"""Group-only services. DirectChat authorization and behavior remain unchanged.

Write order is sorted account/profile locks, then group row. Membership changes,
message allocation and receipts serialize on that group row. No path acquires
new account locks after locking a group. Block-aware reads use one snapshot.
"""
from uuid import uuid4
from services.nova_chat import (
    DirectChat, ChatError, missing, uuid_value, identity, now, timestamp,
    page_size, encode_cursor, decode_cursor,
)

MAX_GROUP_SIZE = 50

# SQL constant; user inputs are always bound parameters. Both block directions
# suppress content without revealing who set the block.
VISIBLE_MESSAGE = '''m.seq>=? AND NOT EXISTS (
    SELECT 1 FROM nova_chat_blocks b WHERE
    (b.blocker_id=? AND b.blocked_id=m.sender_id) OR
    (b.blocker_id=m.sender_id AND b.blocked_id=?))'''


def group_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80 or any(ord(c)<32 for c in value):
        raise ChatError('invalid_name', 'Group name must contain 1–80 characters without control characters.')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise ChatError('invalid_name', 'Invalid group name.') from None
    return value.strip()


class GroupChat(DirectChat):
    def group(self, db, cid):
        row = db.execute("SELECT * FROM nova_chat_conversations WHERE id=? AND kind='group' AND closed_at IS NULL", (uuid_value(cid),)).fetchone()
        if not row:
            missing()
        return row

    def member(self, db, cid, user, states=('active',)):
        row = db.execute('SELECT * FROM nova_chat_members WHERE conversation_id=? AND user_id=?', (cid,user)).fetchone()
        if not row or row['state'] not in states:
            missing()
        return row

    def authorize_group(self, db, user, cid, write=False, extra=(), states=('active',)):
        cid = uuid_value(cid)
        if write:
            self.lock_users(db, [user, *extra])
            db.execute("SELECT id FROM nova_chat_conversations WHERE id=? AND kind='group'" + (' FOR UPDATE' if self.postgres else ''), (cid,)).fetchone()
        self.profile(db,user)
        return self.group(db,cid), self.member(db,cid,user,states)

    def event(self, db, cid, kind, actor, target=None, detail=None):
        row = db.execute('SELECT last_event_seq FROM nova_chat_conversations WHERE id=?', (cid,)).fetchone()
        seq, date = row['last_event_seq']+1, now()
        db.execute('INSERT INTO nova_chat_events(id,conversation_id,seq,kind,actor_id,target_id,detail,created_at) VALUES(?,?,?,?,?,?,?,?)',
                   (str(uuid4()),cid,seq,kind,actor,target,detail,date))
        db.execute('UPDATE nova_chat_conversations SET last_event_seq=?,updated_at=? WHERE id=?', (seq,date,cid))
        return seq

    def staff(self, member):
        if member['role'] not in ('owner','admin'):
            raise ChatError('forbidden', 'Group administration permission is required.',403)

    def owner(self, member):
        if member['role'] != 'owner':
            raise ChatError('forbidden', 'Only the group owner can do this.',403)

    def invite_target(self, db, actor, target):
        self.profile(db,target)
        preference = db.execute('SELECT allow_group_invites FROM nova_profiles WHERE user_id=?', (target,)).fetchone()
        if actor == target or not preference['allow_group_invites'] or self.blocked(db,actor,target):
            missing()

    def add_invitation(self, db, cid, actor, target):
        old = db.execute('SELECT state FROM nova_chat_members WHERE conversation_id=? AND user_id=?', (cid,target)).fetchone()
        if old and old['state'] in ('active','invited'):
            return
        count = db.execute("SELECT COUNT(*) AS n FROM nova_chat_members WHERE conversation_id=? AND state IN ('active','invited')", (cid,)).fetchone()['n']
        if count >= MAX_GROUP_SIZE:
            raise ChatError('group_full','Groups support at most 50 active members and pending invitations.',409)
        self.invite_target(db,actor,target)
        self.rate_limit('group_invite',actor)
        if old:
            db.execute("UPDATE nova_chat_members SET state='invited',role='member',invited_by=?,left_at=NULL WHERE conversation_id=? AND user_id=?", (actor,cid,target))
        else:
            db.execute("INSERT INTO nova_chat_members(conversation_id,user_id,state,joined_at,invited_by) VALUES(?,?,'invited',?,?)", (cid,target,now(),actor))
        self.event(db,cid,'invited',actor,target)

    def create(self, user, name, profile_ids):
        name = group_name(name)
        if not isinstance(profile_ids,list) or len(profile_ids)>49 or any(not isinstance(p,str) for p in profile_ids) or len(set(profile_ids))!=len(profile_ids):
            raise ChatError('invalid_members','Provide at most 49 unique profile IDs.')
        with self.transaction(write=True) as db:
            targets = [self.target(db,p) for p in profile_ids]
            self.lock_users(db,[user,*targets])
            self.profile(db,user)
            for target in targets:
                self.invite_target(db,user,target)
            self.rate_limit('group_create',user)
            cid, date = str(uuid4()), now()
            db.execute("INSERT INTO nova_chat_conversations(id,kind,creator_id,created_at,updated_at,name) VALUES(?,'group',?,?,?,?)", (cid,user,date,date,name))
            db.execute("INSERT INTO nova_chat_members(conversation_id,user_id,role,joined_at) VALUES(?,?,'owner',?)", (cid,user,date))
            self.event(db,cid,'created',user,detail=name)
            for target in targets:
                self.add_invitation(db,cid,user,target)
            return self.summary_group(db,user,*self.authorize_group(db,user,cid))

    def invite(self, user, cid, profile_id):
        with self.transaction(write=True) as db:
            target = self.target(db,profile_id)
            group, member = self.authorize_group(db,user,cid,True,[target])
            self.staff(member)
            self.add_invitation(db,group['id'],user,target)
            return {'invited':True}

    def join(self, user, cid):
        cid = uuid_value(cid)
        with self.transaction(write=True) as db:
            invitation = self.member(db,cid,user,('active','invited'))
            inviter = invitation['invited_by']
            group, member = self.authorize_group(db,user,cid,True,[inviter] if inviter is not None else [],('active','invited'))
            if member['state']=='active':
                return self.summary_group(db,user,group,member)
            if inviter is None or member['invited_by'] != inviter:
                raise ChatError('invitation_changed','Refresh the invitation and try again.',409)
            self.profile(db,inviter)
            self.member(db,cid,inviter)
            if self.blocked(db,user,inviter):
                missing()
            self.rate_limit('group_manage',user)
            # Reset watermarks and both visibility boundaries for every new tenure.
            db.execute("""UPDATE nova_chat_members SET state='active',role='member',joined_at=?,left_at=NULL,
                visible_from_seq=?,visible_event_from=?,last_read_seq=0,last_delivered_seq=0
                WHERE conversation_id=? AND user_id=?""", (now(),group['last_seq']+1,group['last_event_seq']+1,cid,user))
            self.event(db,cid,'joined',user,user)
            return self.summary_group(db,user,*self.authorize_group(db,user,cid))

    def leave(self, user, cid):
        with self.transaction(write=True) as db:
            group, member = self.authorize_group(db,user,cid,True,states=('active','invited'))
            cid = group['id']
            # Leaving/declining is a safety control, never blocked by quotas.
            if member['state']=='invited':
                db.execute("UPDATE nova_chat_members SET state='left',left_at=? WHERE conversation_id=? AND user_id=?", (now(),cid,user))
                self.event(db,cid,'declined',user,user)
                return {'left':True}
            if member['role']=='owner':
                count = db.execute("SELECT COUNT(*) AS n FROM nova_chat_members WHERE conversation_id=? AND state='active'", (cid,)).fetchone()['n']
                if count>1:
                    raise ChatError('transfer_required','Transfer ownership before leaving.',409)
                db.execute("UPDATE nova_chat_members SET state='removed',left_at=? WHERE conversation_id=? AND state='invited'", (now(),cid))
                db.execute('UPDATE nova_chat_conversations SET closed_at=? WHERE id=?', (now(),cid))
                self.event(db,cid,'closed',user)
            db.execute("UPDATE nova_chat_members SET state='left',role='member',left_at=? WHERE conversation_id=? AND user_id=?", (now(),cid,user))
            self.event(db,cid,'left',user,user)
            return {'left':True}

    def remove(self, user, cid, profile_id):
        with self.transaction(write=True) as db:
            target = self.target(db,profile_id)
            group, member = self.authorize_group(db,user,cid,True,[target])
            self.staff(member)
            victim = self.member(db,group['id'],target,('active','invited'))
            if target==user or victim['role']=='owner' or (member['role']=='admin' and victim['role']!='member'):
                raise ChatError('forbidden','You cannot remove this member.',403)
            self.rate_limit('group_manage',user)
            db.execute("UPDATE nova_chat_members SET state='removed',role='member',left_at=? WHERE conversation_id=? AND user_id=?", (now(),group['id'],target))
            self.event(db,group['id'],'removed',user,target)
            return {'removed':True}

    def role(self, user, cid, profile_id, role):
        if role not in ('admin','member'):
            raise ChatError('invalid_role','Use admin or member; ownership uses the transfer endpoint.')
        with self.transaction(write=True) as db:
            target = self.target(db,profile_id)
            group, member = self.authorize_group(db,user,cid,True,[target])
            self.owner(member)
            victim = self.member(db,group['id'],target)
            if victim['role']=='owner':
                raise ChatError('forbidden','Transfer ownership before changing the owner role.',403)
            if victim['role']!=role:
                self.rate_limit('group_manage',user)
                db.execute('UPDATE nova_chat_members SET role=? WHERE conversation_id=? AND user_id=?', (role,group['id'],target))
                self.event(db,group['id'],'role_changed',user,target,role)
            return {'role':role}

    def transfer(self, user, cid, profile_id):
        with self.transaction(write=True) as db:
            target = self.target(db,profile_id)
            group, member = self.authorize_group(db,user,cid,True,[target])
            self.owner(member)
            self.member(db,group['id'],target)
            self.profile(db,target)
            if target!=user:
                self.rate_limit('group_manage',user)
                # Release old unique owner slot before assigning the new owner,
                # inside one transaction; outside readers never see no owner.
                db.execute("UPDATE nova_chat_members SET role='admin' WHERE conversation_id=? AND user_id=?", (group['id'],user))
                db.execute("UPDATE nova_chat_members SET role='owner' WHERE conversation_id=? AND user_id=?", (group['id'],target))
                self.event(db,group['id'],'ownership_transferred',user,target)
            return {'owner':identity(self.profile(db,target))}

    def rename(self, user, cid, name):
        name = group_name(name)
        with self.transaction(write=True) as db:
            group, member = self.authorize_group(db,user,cid,True)
            self.staff(member)
            if group['name']!=name:
                self.rate_limit('group_manage',user)
                db.execute('UPDATE nova_chat_conversations SET name=? WHERE id=?', (name,group['id']))
                self.event(db,group['id'],'renamed',user,detail=name)
            return {'name':name}

    def summary_group(self, db, user, group, member):
        cid = group['id']
        visible = (member['visible_from_seq'],user,user)
        latest = db.execute('SELECT m.* FROM nova_chat_messages m WHERE m.conversation_id=? AND '+VISIBLE_MESSAGE+' ORDER BY m.seq DESC LIMIT 1', (cid,*visible)).fetchone()
        unread = db.execute('SELECT COUNT(*) AS n FROM nova_chat_messages m WHERE m.conversation_id=? AND '+VISIBLE_MESSAGE+' AND m.seq>? AND m.sender_id<>? AND m.deleted_at IS NULL', (cid,*visible,member['last_read_seq'],user)).fetchone()['n']
        return {'id':cid,'kind':'group','name':group['name'],'role':member['role'],
                'created_at':timestamp(group['created_at']),'updated_at':timestamp(group['updated_at']),
                'latest_message':self.message(db,latest) if latest else None,'unread_count':unread,
                'last_read_seq':member['last_read_seq'],'last_delivered_seq':member['last_delivered_seq']}

    def conversation(self, user, cid):
        with self.transaction() as db:
            group, member = self.authorize_group(db,user,cid)
            result = self.summary_group(db,user,group,member)
            roster = db.execute("""SELECT p.id,p.handle,p.display_name,p.user_id,m.role,m.state,m.last_read_seq,m.last_delivered_seq
                FROM nova_chat_members m JOIN nova_profiles p ON p.user_id=m.user_id
                WHERE m.conversation_id=? AND m.state IN ('active','invited') ORDER BY p.handle LIMIT 50""", (group['id'],)).fetchall()
            result['members'] = []
            for person in roster:
                if person['state']=='invited' and member['role']=='member':
                    continue
                entry = dict(identity(person),role=person['role'],state=person['state'])
                if person['state']=='active' and not self.blocked(db,user,person['user_id']):
                    entry['receipts'] = {key:person[key] if person[key]>=member['visible_from_seq'] else 0 for key in ('last_read_seq','last_delivered_seq')}
                result['members'].append(entry)
            return result

    def groups(self, user, cursor=None, limit=50, invitations=False):
        limit = page_size(limit)
        with self.transaction() as db:
            profile = self.profile(db,user)
            scope = ('group-invites:' if invitations else 'groups:')+str(profile['id'])
            after = ''
            parameters = [user,'invited' if invitations else 'active']
            invitation_filter = ''
            if invitations:
                invitation_filter = ''' AND NOT EXISTS(SELECT 1 FROM nova_chat_blocks b WHERE
                    (b.blocker_id=m.user_id AND b.blocked_id=m.invited_by) OR
                    (b.blocker_id=m.invited_by AND b.blocked_id=m.user_id))'''
            if cursor:
                data = decode_cursor(cursor,scope)
                if set(data)!={'scope','before'}:
                    raise ChatError('invalid_cursor','Invalid group cursor.')
                after=' AND c.id<?'
                parameters.append(uuid_value(data['before']))
            rows = db.execute("""SELECT c.* FROM nova_chat_conversations c JOIN nova_chat_members m ON m.conversation_id=c.id
                WHERE m.user_id=? AND m.state=? AND c.kind='group' AND c.closed_at IS NULL"""+invitation_filter+after+' ORDER BY c.id DESC LIMIT ?', (*parameters,limit+1)).fetchall()
            more, rows = len(rows)>limit, rows[:limit]
            results=[]
            for group in rows:
                member=self.member(db,group['id'],user,('invited',) if invitations else ('active',))
                if invitations:
                    inviter=member['invited_by']
                    results.append({'id':group['id'],'name':group['name'],'inviter':identity(self.profile(db,inviter,False)) if inviter else None})
                else:
                    results.append(self.summary_group(db,user,group,member))
            return {'invitations' if invitations else 'groups':results,'has_more':more,
                    'next_cursor':encode_cursor({'scope':scope,'before':rows[-1]['id']}) if more else None}

    def messages(self, user, cid, cursor=None, limit=50):
        limit = page_size(limit)
        with self.transaction() as db:
            group, member = self.authorize_group(db,user,cid)
            scope='group-messages:'+group['id']
            before=group['last_seq']+1
            if cursor:
                data=decode_cursor(cursor,scope)
                before=data.get('before')
                if set(data)!={'scope','before'} or type(before) is not int or not 1<=before<=9223372036854775807:
                    raise ChatError('invalid_cursor','Invalid message cursor.')
            rows=db.execute('SELECT m.* FROM nova_chat_messages m WHERE m.conversation_id=? AND '+VISIBLE_MESSAGE+' AND m.seq<? ORDER BY m.seq DESC LIMIT ?',
                (group['id'],member['visible_from_seq'],user,user,before,limit+1)).fetchall()
            more,rows=len(rows)>limit,rows[:limit]
            return {'messages':[self.message(db,r) for r in reversed(rows)],'has_more':more,
                    'next_cursor':encode_cursor({'scope':scope,'before':rows[-1]['seq']}) if more else None}

    def send(self, user, cid, data):
        if not isinstance(data,dict) or set(data)!={'client_message_id','type','text'}:
            raise ChatError('invalid_request','Provide client_message_id, type and text.')
        client_id=uuid_value(data['client_message_id'])
        text=data['text']
        try:
            valid=isinstance(text,str) and 0<len(text)<=4000 and bool(text.strip()) and '\x00' not in text and len(text.encode('utf-8'))<=16384
        except UnicodeError:
            valid=False
        if not valid:
            raise ChatError('invalid_text','Text must be nonempty and at most 4,000 characters / 16 KiB.')
        with self.transaction(write=True) as db:
            group, member=self.authorize_group(db,user,cid,True)
            prior=db.execute('SELECT * FROM nova_chat_messages WHERE conversation_id=? AND sender_id=? AND client_message_id=?', (group['id'],user,client_id)).fetchone()
            if prior:
                if prior['seq']<member['visible_from_seq'] or prior['text']!=text or prior['type']!=data['type']:
                    raise ChatError('message_conflict','Client message ID cannot be reused.',409)
                return self.message(db,prior)
            if data['type']!='text':
                raise ChatError('invalid_type','Only text messages are supported.')
            self.rate_limit('send',user)
            mid, seq, date=str(uuid4()),group['last_seq']+1,now()
            db.execute('INSERT INTO nova_chat_messages(id,conversation_id,seq,sender_id,client_message_id,type,text,created_at) VALUES(?,?,?,?,?,?,?,?)', (mid,group['id'],seq,user,client_id,'text',text,date))
            db.execute('UPDATE nova_chat_conversations SET last_seq=?,last_message_seq=?,updated_at=? WHERE id=?', (seq,seq,date,group['id']))
            return self.message(db,db.execute('SELECT * FROM nova_chat_messages WHERE id=?',(mid,)).fetchone())

    def receipts(self, user, cid, data):
        if not isinstance(data,dict) or not data or set(data)-{'delivered_through_seq','read_through_seq'} or any(type(v) is not int or not 0<=v<=9223372036854775807 for v in data.values()):
            raise ChatError('invalid_receipt','Provide nonnegative receipt watermarks only.')
        with self.transaction(write=True) as db:
            group, member=self.authorize_group(db,user,cid,True)
            for seq in data.values():
                if seq and not db.execute('SELECT m.id FROM nova_chat_messages m WHERE m.conversation_id=? AND m.seq=? AND '+VISIBLE_MESSAGE,
                    (group['id'],seq,member['visible_from_seq'],user,user)).fetchone():
                    raise ChatError('invalid_receipt','Receipt must reference a visible message.')
            read=max(member['last_read_seq'],data.get('read_through_seq',0))
            delivered=max(member['last_delivered_seq'],data.get('delivered_through_seq',0),read)
            db.execute('UPDATE nova_chat_members SET last_read_seq=?,last_delivered_seq=? WHERE conversation_id=? AND user_id=?', (read,delivered,group['id'],user))
            return {'last_read_seq':read,'last_delivered_seq':delivered}

    def events(self, user, cid, cursor=None, limit=50):
        limit=page_size(limit)
        with self.transaction() as db:
            group,member=self.authorize_group(db,user,cid)
            scope='group-events:'+group['id']
            before=group['last_event_seq']+1
            if cursor:
                data=decode_cursor(cursor,scope)
                before=data.get('before')
                if set(data)!={'scope','before'} or type(before) is not int or not 1<=before<=9223372036854775807:
                    raise ChatError('invalid_cursor','Invalid event cursor.')
            rows=db.execute('SELECT * FROM nova_chat_events WHERE conversation_id=? AND seq>=? AND seq<? ORDER BY seq DESC LIMIT ?', (group['id'],member['visible_event_from'],before,limit+1)).fetchall()
            more,rows=len(rows)>limit,rows[:limit]
            results=[]
            for row in reversed(rows):
                entry={k:row[k] for k in ('id','seq','kind','detail')}
                entry['created_at']=timestamp(row['created_at'])
                for field in ('actor','target'):
                    person=db.execute('SELECT id,handle,display_name FROM nova_profiles WHERE user_id=?',(row[field+'_id'],)).fetchone()
                    entry[field]=identity(person) if person else None
                results.append(entry)
            return {'events':results,'has_more':more,'next_cursor':encode_cursor({'scope':scope,'before':rows[-1]['seq']}) if more else None}
