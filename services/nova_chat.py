"""Direct messaging services. All authority derives from authenticated user ID.

Mutation lock order: ordered account rows, ordered profile rows, conversation.
SQLite uses BEGIN IMMEDIATE. All participating writers use database locks, not
process mutexes; a committed block excludes every subsequently committed send.
"""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import re
from uuid import UUID, uuid4


class ChatError(ValueError):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def missing():
    raise ChatError('not_found', 'Conversation or profile is unavailable.', 404)


def uuid_value(value):
    try:
        if not isinstance(value, str) or len(value) != 36:
            raise ValueError()
        return str(UUID(value))
    except (ValueError, AttributeError):
        raise ChatError('invalid_id', 'Expected a UUID.') from None


def public_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', value) or int(value) > 2147483647:
        raise ChatError('invalid_id', 'Invalid profile identifier.')
    return int(value)


def timestamp(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec='microseconds')
    return value


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def identity(row):
    return {'id': str(row['id']), 'handle': row['handle'], 'display_name': row['display_name']}


def page_size(value):
    try:
        if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,3}', str(value)):
            raise ValueError()
        size = int(value)
        if not 1 <= size <= 100:
            raise ValueError()
        return size
    except (ValueError, TypeError):
        raise ChatError('invalid_limit', 'Limit must be between 1 and 100.') from None


def encode_cursor(data):
    return base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).decode().rstrip('=')


def decode_cursor(value, scope):
    try:
        if not isinstance(value, str) or not 1 <= len(value) <= 512:
            raise ValueError()
        data = json.loads(base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True))
        if not isinstance(data, dict) or data.get('scope') != scope:
            raise ValueError()
        return data
    except (ValueError, TypeError, UnicodeError):
        raise ChatError('invalid_cursor', 'Invalid pagination cursor.') from None


class DirectChat:
    def __init__(self, get_db, postgres=False, rate_limit=None):
        self.get_db, self.postgres = get_db, postgres
        self.rate_limit = rate_limit or (lambda category, user: None)

    @contextmanager
    def transaction(self, write=False):
        db = self.get_db()
        try:
            if not self.postgres:
                # Enforce social FKs without changing the application's global helper.
                db.execute('PRAGMA foreign_keys=ON')
            if write and not self.postgres:
                db.execute('BEGIN IMMEDIATE')
            elif write:
                db.execute("SET LOCAL lock_timeout = '5s'")
                db.execute("SET LOCAL statement_timeout = '15s'")
            elif not write and self.postgres:
                db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            elif not write:
                db.execute('BEGIN')
            yield db
            if write:
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def lock_users(self, db, users):
        for user in sorted(set(users)):
            row = db.execute('SELECT id FROM users WHERE id=?' + (' FOR UPDATE' if self.postgres else ''), (user,)).fetchone()
            if not row:
                missing()
        for user in sorted(set(users)):
            db.execute('SELECT id FROM nova_profiles WHERE user_id=?' + (' FOR UPDATE' if self.postgres else ''), (user,)).fetchone()

    def profile(self, db, user, active=True):
        row = db.execute('SELECT id,user_id,handle,display_name,status,discoverable FROM nova_profiles WHERE user_id=?', (user,)).fetchone()
        if not row or (active and row['status'] != 'active'):
            missing()
        return row

    def target(self, db, profile_id):
        row = db.execute('SELECT user_id FROM nova_profiles WHERE id=?', (public_id(profile_id),)).fetchone()
        if not row:
            missing()
        return row['user_id']

    def blocked(self, db, a, b):
        return db.execute('SELECT id FROM nova_chat_blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)', (a,b,b,a)).fetchone() is not None

    def authorize(self, db, user, cid, write=False):
        cid = uuid_value(cid)
        row = db.execute('''SELECT c.*, m.visible_from_seq, m.last_read_seq, m.last_delivered_seq
            FROM nova_chat_conversations c JOIN nova_chat_members m ON m.conversation_id=c.id
            WHERE c.id=? AND c.kind='direct' AND m.user_id=? AND m.state='active'
              AND (c.direct_low=? OR c.direct_high=?)''', (cid,user,user,user)).fetchone()
        if not row:
            missing()
        if write:
            self.lock_users(db, [row['direct_low'], row['direct_high']])
            db.execute('SELECT id FROM nova_chat_conversations WHERE id=?' + (' FOR UPDATE' if self.postgres else ''), (cid,)).fetchone()
            # Re-read after waiting for locks: earlier reads are not authority.
            return self.authorize(db, user, cid)
        self.profile(db, user)
        return row

    def message(self, db, row):
        sender = db.execute('SELECT id,handle,display_name FROM nova_profiles WHERE user_id=?', (row['sender_id'],)).fetchone()
        return {'id': row['id'], 'conversation_id': row['conversation_id'], 'seq': row['seq'],
                'sender': identity(sender) if sender else None, 'client_message_id': row['client_message_id'],
                'type': row['type'], 'text': row['text'] if not row['deleted_at'] else None,
                'created_at': timestamp(row['created_at']), 'edited_at': timestamp(row['edited_at']),
                'deleted_at': timestamp(row['deleted_at'])}

    def summary(self, db, user, row):
        other = row['direct_high'] if user == row['direct_low'] else row['direct_low']
        peer = self.profile(db, other, active=False)
        latest = db.execute('SELECT * FROM nova_chat_messages WHERE conversation_id=? AND seq>=? ORDER BY seq DESC LIMIT 1', (row['id'],row['visible_from_seq'])).fetchone()
        unread = db.execute('''SELECT COUNT(*) AS n FROM nova_chat_messages WHERE conversation_id=?
            AND seq>? AND seq>=? AND sender_id<>? AND deleted_at IS NULL''',
            (row['id'], row['last_read_seq'], row['visible_from_seq'], user)).fetchone()['n']
        receipts = db.execute("SELECT last_read_seq,last_delivered_seq FROM nova_chat_members WHERE conversation_id=? AND user_id=? AND state='active'", (row['id'], other)).fetchone()
        return {'id':row['id'], 'kind':'direct', 'participant':identity(peer),
                'latest_message':self.message(db, latest) if latest else None, 'unread_count':unread,
                'updated_at':timestamp(row['updated_at']), 'created_at':timestamp(row['created_at']),
                'last_read_seq':row['last_read_seq'], 'last_delivered_seq':row['last_delivered_seq'],
                'peer_receipts':dict(receipts) if receipts and not self.blocked(db,user,other) else None}

    def direct(self, user, recipient_id):
        with self.transaction(write=True) as db:
            other = self.target(db, recipient_id)
            if user == other:
                raise ChatError('self_conversation', 'Choose another profile.')
            self.lock_users(db, [user,other])
            self.profile(db,user)
            peer = self.profile(db,other)
            if self.blocked(db,user,other):
                missing()
            low,high = sorted([user,other])
            row = db.execute("SELECT id FROM nova_chat_conversations WHERE direct_low=? AND direct_high=? AND kind='direct'", (low,high)).fetchone()
            if row:
                cid = row['id']
            else:
                if not peer['discoverable']:
                    missing()
                self.rate_limit('create', user)
                cid, date = str(uuid4()), now()
                db.execute("INSERT INTO nova_chat_conversations(id,kind,creator_id,direct_low,direct_high,created_at,updated_at) VALUES(?,'direct',?,?,?,?,?)", (cid,user,low,high,date,date))
                for member in (low,high):
                    db.execute('INSERT INTO nova_chat_members(conversation_id,user_id,joined_at) VALUES(?,?,?)', (cid,member,date))
            return self.summary(db,user,self.authorize(db,user,cid))

    def conversation(self, user, cid):
        with self.transaction() as db:
            return self.summary(db,user,self.authorize(db,user,cid))

    def conversations(self, user, cursor=None, limit=50):
        limit = page_size(limit)
        with self.transaction() as db:
            profile = self.profile(db,user)
            scope = 'list:profile:' + str(profile['id'])
            parameters = [user]
            boundary = ''
            if cursor:
                data = decode_cursor(cursor, scope)
                try:
                    if set(data) != {'scope','date','id'}:
                        raise ValueError()
                    date = datetime.fromisoformat(data['date'])
                    if not date.tzinfo: raise ValueError()
                    cid = uuid_value(data['id'])
                except (ValueError, TypeError, KeyError):
                    raise ChatError('invalid_cursor','Invalid pagination cursor.') from None
                boundary = ' AND (c.created_at < ? OR (c.created_at=? AND c.id<?))'
                parameters.extend([data['date'], data['date'], cid])
            rows = db.execute('''SELECT c.*,m.visible_from_seq,m.last_read_seq,m.last_delivered_seq
                FROM nova_chat_conversations c JOIN nova_chat_members m ON m.conversation_id=c.id
                WHERE m.user_id=? AND m.state='active' AND c.kind='direct' ''' + boundary +
                ' ORDER BY c.created_at DESC,c.id DESC LIMIT ?', (*parameters,limit+1)).fetchall()
            more, rows = len(rows)>limit, rows[:limit]
            next_cursor = encode_cursor({'scope':scope,'date':timestamp(rows[-1]['created_at']),'id':rows[-1]['id']}) if more else None
            return {'conversations':[self.summary(db,user,r) for r in rows], 'has_more':more,'next_cursor':next_cursor}

    def messages(self, user, cid, cursor=None, limit=50):
        limit = page_size(limit)
        with self.transaction() as db:
            member = self.authorize(db,user,cid)
            before = member['last_seq'] + 1
            if cursor:
                data = decode_cursor(cursor, 'messages:'+member['id'])
                before = data.get('before')
                if set(data) != {'scope','before'} or type(before) is not int or not 1 <= before <= 9223372036854775807:
                    raise ChatError('invalid_cursor','Invalid pagination cursor.')
            rows = db.execute('SELECT * FROM nova_chat_messages WHERE conversation_id=? AND seq>=? AND seq<? ORDER BY seq DESC LIMIT ?', (member['id'],member['visible_from_seq'],before,limit+1)).fetchall()
            more, rows = len(rows)>limit, rows[:limit]
            next_cursor = encode_cursor({'scope':'messages:'+member['id'],'before':rows[-1]['seq']}) if more else None
            return {'messages':[self.message(db,r) for r in reversed(rows)],'has_more':more,'next_cursor':next_cursor}

    def send(self, user, cid, data):
        if not isinstance(data,dict) or set(data) != {'client_message_id','type','text'}:
            raise ChatError('invalid_request','Provide client_message_id, type and text.')
        client_id = uuid_value(data['client_message_id'])
        text = data['text']
        try:
            valid = isinstance(text,str) and 0 < len(text) <= 4000 and bool(text.strip()) and '\x00' not in text and len(text.encode('utf-8')) <= 16384
        except UnicodeError:
            valid = False
        if not valid:
            raise ChatError('invalid_text','Text must be nonempty and at most 4,000 characters / 16 KiB.')
        with self.transaction(write=True) as db:
            row = self.authorize(db,user,cid,write=True)
            other = row['direct_high'] if user==row['direct_low'] else row['direct_low']
            self.profile(db,other)
            if self.blocked(db,user,other): missing()
            prior = db.execute('SELECT * FROM nova_chat_messages WHERE conversation_id=? AND sender_id=? AND client_message_id=?', (row['id'],user,client_id)).fetchone()
            if prior:
                if prior['text'] != text or prior['type'] != data['type']:
                    raise ChatError('message_conflict','Client message ID was already used for different content.',409)
                return self.message(db,prior)
            if data['type'] != 'text':
                raise ChatError('invalid_type','Only text messages are supported.')
            self.rate_limit('send',user)
            mid, date, seq = str(uuid4()), now(), row['last_seq']+1
            db.execute('INSERT INTO nova_chat_messages(id,conversation_id,seq,sender_id,client_message_id,type,text,created_at) VALUES(?,?,?,?,?,?,?,?)', (mid,row['id'],seq,user,client_id,'text',text,date))
            db.execute('UPDATE nova_chat_conversations SET last_seq=?,last_message_seq=?,updated_at=? WHERE id=?', (seq,seq,date,row['id']))
            return self.message(db,db.execute('SELECT * FROM nova_chat_messages WHERE id=?',(mid,)).fetchone())

    def receipts(self, user, cid, data):
        if not isinstance(data,dict) or not data or set(data)-{'delivered_through_seq','read_through_seq'}:
            raise ChatError('invalid_request','Provide receipt watermarks only.')
        if any(type(v) is not int or not 0 <= v <= 9223372036854775807 for v in data.values()):
            raise ChatError('invalid_receipt','Receipt sequences must be nonnegative integers.')
        with self.transaction(write=True) as db:
            row = self.authorize(db,user,cid,write=True)
            other = row['direct_high'] if user==row['direct_low'] else row['direct_low']
            if self.blocked(db,user,other): missing()
            for seq in data.values():
                if seq and not db.execute('SELECT id FROM nova_chat_messages WHERE conversation_id=? AND seq=? AND seq>=?',(row['id'],seq,row['visible_from_seq'])).fetchone():
                    raise ChatError('invalid_receipt','Receipt exceeds visible messages.')
            read = max(row['last_read_seq'],data.get('read_through_seq',0))
            delivered = max(row['last_delivered_seq'],data.get('delivered_through_seq',0),read)
            db.execute('UPDATE nova_chat_members SET last_read_seq=?,last_delivered_seq=? WHERE conversation_id=? AND user_id=?', (read,delivered,row['id'],user))
            return {'last_read_seq':read,'last_delivered_seq':delivered}

    def block(self, user, profile_id, remove=False):
        with self.transaction(write=True) as db:
            other = self.target(db,profile_id)
            if other == user: raise ChatError('self_block','Cannot block your own profile.')
            self.lock_users(db,[user,other])
            self.profile(db,user)
            if remove:
                db.execute('DELETE FROM nova_chat_blocks WHERE blocker_id=? AND blocked_id=?',(user,other))
            elif not db.execute('SELECT id FROM nova_chat_blocks WHERE blocker_id=? AND blocked_id=?',(user,other)).fetchone():
                db.execute('INSERT INTO nova_chat_blocks(blocker_id,blocked_id,created_at) VALUES(?,?,?)',(user,other,now()))
            return {'blocked':not remove}

    def blocks(self, user, cursor=None, limit=50):
        limit = page_size(limit)
        before = 2147483648
        with self.transaction() as db:
            profile = self.profile(db,user)
            scope = 'blocks:profile:' + str(profile['id'])
            if cursor:
                data = decode_cursor(cursor,scope)
                before = data.get('before')
                if set(data) != {'scope','before'} or type(before) is not int or not 1 <= before <= 2147483648:
                    raise ChatError('invalid_cursor','Invalid pagination cursor.')
            rows = db.execute('''SELECT p.id,p.handle,p.display_name,b.id AS block_id FROM nova_chat_blocks b
                JOIN nova_profiles p ON p.user_id=b.blocked_id WHERE b.blocker_id=? AND b.id<?
                ORDER BY b.id DESC LIMIT ?''',(user,before,limit+1)).fetchall()
            more, rows = len(rows)>limit, rows[:limit]
            return {'blocks':[identity(r) for r in rows], 'has_more':more,
                    'next_cursor':encode_cursor({'scope':scope,'before':rows[-1]['block_id']}) if more else None}

    def search(self, user, query):
        if not isinstance(query,str) or not re.fullmatch(r'[A-Za-z0-9_]{3,30}',query):
            raise ChatError('invalid_query','Search using 3–30 handle characters.')
        self.rate_limit('search',user)
        prefix = query.lower().replace('_','\\_') + '%'
        with self.transaction() as db:
            self.profile(db,user)
            rows = db.execute('''SELECT p.id,p.handle,p.display_name FROM nova_profiles p
                WHERE p.user_id<>? AND p.discoverable=1 AND p.status='active' AND p.handle LIKE ? ESCAPE '\\'
                AND NOT EXISTS(SELECT 1 FROM nova_chat_blocks b WHERE
                    (b.blocker_id=? AND b.blocked_id=p.user_id) OR (b.blocker_id=p.user_id AND b.blocked_id=?))
                ORDER BY p.handle LIMIT 20''',(user,prefix,user,user)).fetchall()
            return {'users':[identity(r) for r in rows]}
