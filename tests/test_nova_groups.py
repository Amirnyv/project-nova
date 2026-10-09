"""Group contract shared by SQLite and disposable PostgreSQL tests."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from flask import Flask
from flask_login import LoginManager, UserMixin
from services.nova_chat import DirectChat, ChatError, encode_cursor
from services.nova_chat_routes import register_nova_chat, ChatRateLimiter
from services.nova_group_schema import migrate_nova_groups
from services.nova_groups import GroupChat
from services.nova_profile_schema import migrate_nova_profiles
from services.nova_chat_schema import migrate_nova_chat
from services.nova_profiles import claim_profile


class GroupContract:
    def prepare_groups(self):
        self.ids={}
        for user,name in [(1,'alice'),(2,'bobby'),(3,'carol'),(4,'david')]:
            profile=claim_profile(self.connect,user,name,postgres=self.postgres,discoverable=True,allow_group_invites=True)
            db=self.connect()
            public=int(profile['id'])+100
            db.execute('UPDATE nova_profiles SET id=? WHERE user_id=?',(public,user))
            db.commit();db.close()
            self.ids[user]=str(public)
        db=self.connect();migrate_nova_chat(db,self.postgres);migrate_nova_groups(db,self.postgres);db.close()
        self.groups=GroupChat(self.connect,self.postgres)
        self.direct=DirectChat(self.connect,self.postgres)

    def sql(self,sql,args=()):
        db=self.connect()
        try:db.execute(sql,args);db.commit()
        finally:db.close()

    def failure(self,status,call):
        with self.assertRaises(ChatError) as caught:call()
        self.assertEqual(caught.exception.status,status)

    def create(self,members=(2,3),join=True):
        cid=self.groups.create(1,'Study group',[self.ids[u] for u in members])['id']
        if join:
            for user in members:self.groups.join(user,cid)
        return cid

    def send(self,cid,user=1,text='Hello group',key=None):
        return self.groups.send(user,cid,{'type':'text','text':text,'client_message_id':key or str(uuid4())})

    def test_creation_invitation_acceptance(self):
        cid=self.create(join=False)
        self.assertEqual(self.groups.conversation(1,cid)['role'],'owner')
        self.assertEqual(self.groups.groups(2)['groups'],[])
        self.assertEqual(self.groups.groups(2,invitations=True)['invitations'][0]['id'],cid)
        for call in [lambda:self.groups.conversation(2,cid),lambda:self.groups.messages(2,cid),lambda:self.send(cid,2)]:
            self.failure(404,call)
        self.groups.join(2,cid);self.groups.join(2,cid)
        self.assertEqual(self.groups.conversation(2,cid)['role'],'member')
        self.assertEqual(len(self.groups.conversation(2,cid)['members']),2)
        self.failure(404,lambda:self.groups.join(4,cid))
        self.groups.leave(3,cid)
        self.assertEqual(self.groups.groups(3,invitations=True)['invitations'],[])

    def test_invite_preferences_and_blocking(self):
        cid=self.create((),False)
        self.sql('UPDATE nova_profiles SET allow_group_invites=0 WHERE user_id=2')
        self.failure(404,lambda:self.groups.invite(1,cid,self.ids[2]))
        self.sql('UPDATE nova_profiles SET allow_group_invites=1 WHERE user_id=2')
        self.direct.block(2,self.ids[1])
        self.failure(404,lambda:self.groups.invite(1,cid,self.ids[2]))
        self.direct.block(2,self.ids[1],remove=True)
        self.groups.invite(1,cid,self.ids[2]);self.groups.invite(1,cid,self.ids[2])
        self.direct.block(1,self.ids[2])
        self.assertEqual(self.groups.groups(2,invitations=True)['invitations'],[])
        self.failure(404,lambda:self.groups.join(2,cid))
        self.direct.block(1,self.ids[2],remove=True)
        self.groups.join(2,cid)

    def test_roles_and_removal(self):
        cid=self.create()
        self.failure(403,lambda:self.groups.invite(2,cid,self.ids[4]))
        self.failure(403,lambda:self.groups.rename(2,cid,'New name'))
        self.failure(403,lambda:self.groups.role(2,cid,self.ids[3],'admin'))
        self.groups.role(1,cid,self.ids[2],'admin')
        self.groups.rename(2,cid,'New name')
        self.groups.invite(2,cid,self.ids[4]);self.groups.join(4,cid)
        self.failure(403,lambda:self.groups.remove(2,cid,self.ids[1]))
        self.groups.role(1,cid,self.ids[3],'admin')
        self.failure(403,lambda:self.groups.remove(2,cid,self.ids[3]))
        self.failure(400,lambda:self.groups.role(1,cid,self.ids[2],'owner'))
        self.failure(403,lambda:self.groups.role(1,cid,self.ids[1],'member'))
        self.groups.remove(2,cid,self.ids[4])
        self.failure(404,lambda:self.groups.messages(4,cid))
        self.groups.remove(1,cid,self.ids[2])
        self.failure(404,lambda:self.groups.invite(2,cid,self.ids[4]))

    def test_transfer_and_leave(self):
        cid=self.create()
        self.failure(409,lambda:self.groups.leave(1,cid))
        self.failure(403,lambda:self.groups.transfer(2,cid,self.ids[3]))
        self.groups.transfer(1,cid,self.ids[2])
        self.assertEqual(self.groups.conversation(2,cid)['role'],'owner')
        self.assertEqual(self.groups.conversation(1,cid)['role'],'admin')
        self.groups.leave(1,cid)
        self.failure(404,lambda:self.groups.conversation(1,cid))
        self.groups.leave(3,cid)
        self.groups.leave(2,cid)
        self.failure(404,lambda:self.groups.conversation(2,cid))

    def test_owner_closes_and_cancels_pending(self):
        cid=self.create((2,),False)
        self.groups.leave(1,cid)
        self.assertEqual(self.groups.groups(2,invitations=True)['invitations'],[])
        self.failure(404,lambda:self.groups.join(2,cid))

    def test_history_boundaries_and_retry_after_rejoin(self):
        cid=self.create((2,),False)
        self.send(cid,text='Before joining')
        self.groups.rename(1,cid,'Private earlier name')
        self.groups.join(2,cid)
        self.assertEqual(self.groups.messages(2,cid)['messages'],[])
        self.assertEqual([e['kind'] for e in self.groups.events(2,cid)['events']],['joined'])
        key=str(uuid4());old=self.send(cid,2,key=key)
        self.groups.remove(1,cid,self.ids[2]);self.send(cid,text='While removed')
        for call in [lambda:self.groups.messages(2,cid),lambda:self.groups.events(2,cid),lambda:self.groups.receipts(2,cid,{'read_through_seq':1})]:
            self.failure(404,call)
        self.groups.invite(1,cid,self.ids[2]);self.groups.join(2,cid)
        self.failure(409,lambda:self.send(cid,2,key=key))
        newest=self.send(cid,text='After rejoining')
        self.assertEqual([m['id'] for m in self.groups.messages(2,cid)['messages']],[newest['id']])
        self.failure(400,lambda:self.groups.receipts(2,cid,{'read_through_seq':old['seq']}))
        self.assertEqual(self.groups.conversation(2,cid)['last_read_seq'],0)

    def test_shared_group_block_visibility(self):
        cid=self.create()
        self.send(cid,2,text='bobby');self.send(cid,3,text='carol')
        self.direct.block(1,self.ids[2])
        self.assertEqual([m['text'] for m in self.groups.messages(1,cid)['messages']],['carol'])
        self.send(cid,text='alice');self.send(cid,2,text='still allowed')
        self.assertEqual(len(self.groups.messages(3,cid)['messages']),4)
        self.assertNotIn('alice',[m['text'] for m in self.groups.messages(2,cid)['messages']])
        summary=self.groups.conversation(1,cid)
        self.assertEqual(summary['latest_message']['text'],'alice')
        peer=next(p for p in summary['members'] if p['id']==self.ids[2])
        self.assertNotIn('receipts',peer)
        self.assertEqual(summary['unread_count'],1)
        self.failure(400,lambda:self.groups.receipts(1,cid,{'read_through_seq':4}))
        self.groups.leave(2,cid)
        self.failure(404,lambda:self.send(cid,2))

    def test_pages_order_receipts(self):
        cid=self.create()
        for i in range(7):self.send(cid,text=str(i))
        first=self.groups.messages(2,cid,limit=3)
        second=self.groups.messages(2,cid,cursor=first['next_cursor'],limit=3)
        self.assertEqual([m['seq'] for m in first['messages']],[5,6,7])
        self.assertEqual([m['seq'] for m in second['messages']],[2,3,4])
        self.failure(400,lambda:self.groups.messages(2,cid,cursor='bad'))
        self.failure(400,lambda:self.groups.messages(2,cid,cursor=encode_cursor({'scope':'other','before':3})))
        self.failure(400,lambda:self.groups.messages(2,cid,limit=101))
        result=self.groups.receipts(2,cid,{'read_through_seq':7})
        self.assertEqual(result,{'last_read_seq':7,'last_delivered_seq':7})
        self.assertEqual(self.groups.receipts(2,cid,{'read_through_seq':1}),result)
        self.failure(400,lambda:self.groups.receipts(2,cid,{'read_through_seq':8}))
        self.failure(400,lambda:self.groups.receipts(2,cid,{'read_through_seq':1,'user_id':1}))
        self.assertEqual(self.groups.conversation(2,cid)['unread_count'],0)

    def test_event_history_and_pagination(self):
        cid=self.create()
        self.groups.role(1,cid,self.ids[2],'admin')
        self.groups.rename(2,cid,'Renamed')
        self.groups.transfer(1,cid,self.ids[2])
        self.groups.leave(3,cid)
        page=self.groups.events(1,cid,limit=2)
        self.assertEqual([e['kind'] for e in page['events']],['ownership_transferred','left'])
        next_page=self.groups.events(1,cid,cursor=page['next_cursor'],limit=2)
        self.assertEqual([e['kind'] for e in next_page['events']],['role_changed','renamed'])
        self.failure(400,lambda:self.groups.events(1,cid,cursor='bad'))
        dump=json.dumps(page)
        for private in ['user_id','actor_id','target_id','email','password_hash']:
            self.assertNotIn('"'+private+'"',dump)

    def test_concurrent_send_retries_and_membership(self):
        cid=self.create()
        with ThreadPoolExecutor(4) as pool:
            results=list(pool.map(lambda i:self.send(cid,(i%3)+1,text=str(i)),range(12)))
        self.assertEqual(sorted(r['seq'] for r in results),list(range(1,13)))
        key=str(uuid4())
        with ThreadPoolExecutor(3) as pool:
            results=list(pool.map(lambda _:self.send(cid,2,key=key),range(3)))
        self.assertEqual(len({r['id'] for r in results}),1)
        self.failure(409,lambda:self.send(cid,2,text='different',key=key))
        def send_or_removed():
            try:return self.send(cid,2)
            except ChatError as error:self.assertEqual(error.status,404)
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(send_or_removed)
            b=pool.submit(self.groups.remove,1,cid,self.ids[2])
            a.result();b.result()
        self.failure(404,lambda:self.send(cid,2))

    def test_concurrent_owner_transfer(self):
        cid=self.create()
        def transfer(target):
            try:self.groups.transfer(1,cid,self.ids[target]);return 200
            except ChatError as error:return error.status
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(transfer,[2,3]))
        self.assertEqual(sorted(results),[200,403])
        db=self.connect()
        try:self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM nova_chat_members WHERE conversation_id=? AND role='owner' AND state='active'",(cid,)).fetchone()['n'],1)
        finally:db.close()

    def test_join_removal_and_block_races(self):
        cid=self.create((2,),False)
        def accept():
            try:self.groups.join(2,cid);return 200
            except ChatError as error:return error.status
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(accept)
            b=pool.submit(self.groups.remove,1,cid,self.ids[2])
            self.assertIn(a.result(),(200,404));b.result()
        self.failure(404,lambda:self.groups.messages(2,cid))
        self.groups.invite(1,cid,self.ids[2])
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(accept)
            b=pool.submit(self.direct.block,1,self.ids[2])
            self.assertIn(a.result(),(200,404));b.result()
        # If acceptance serialized first the member stays, but blocked content
        # is hidden. If blocking serialized first, acceptance is rejected.
        self.send(cid,text='Not visible to blocked peer')
        try:self.assertEqual(self.groups.messages(2,cid)['messages'],[])
        except ChatError as error:self.assertEqual(error.status,404)

    def test_group_migration_preserves_direct_rows(self):
        dm=self.direct.direct(1,self.ids[2])['id']
        data={'type':'text','text':'Direct history','client_message_id':str(uuid4())}
        message=self.direct.send(1,dm,data)
        db=self.connect()
        try:migrate_nova_groups(db,self.postgres)
        finally:db.close()
        self.assertEqual(self.direct.messages(2,dm)['messages'],[message])

    def test_transfer_failure_rolls_back(self):
        cid=self.create()
        original=self.connect
        class FailingConnection:
            def __init__(self):self.db=original()
            def __getattr__(self,name):return getattr(self.db,name)
            def execute(self,sql,args=()):
                if "SET role='owner'" in sql:raise RuntimeError('synthetic failure')
                return self.db.execute(sql,args)
        broken=GroupChat(FailingConnection,self.postgres)
        with self.assertRaises(RuntimeError):broken.transfer(1,cid,self.ids[2])
        self.assertEqual(self.groups.conversation(1,cid)['role'],'owner')
        self.assertEqual(self.groups.conversation(2,cid)['role'],'member')

    def test_size_and_concurrent_invites(self):
        cid=self.create((2,),True)
        def invite(target):
            try:self.groups.invite(1,cid,self.ids[target]);return 200
            except ChatError as error:return error.status
        with patch('services.nova_groups.MAX_GROUP_SIZE',3):
            with ThreadPoolExecutor(2) as pool:results=list(pool.map(invite,[3,4]))
        self.assertEqual(sorted(results),[200,409])
        self.failure(400,lambda:self.groups.create(1,'Large',[str(i) for i in range(50)]))

    def test_idor_profile_status_and_direct_isolation(self):
        cid=self.create((2,))
        for call in [lambda:self.groups.conversation(3,cid),lambda:self.groups.messages(3,cid),
                     lambda:self.groups.events(3,cid),lambda:self.send(cid,3),
                     lambda:self.groups.receipts(3,cid,{'read_through_seq':0}),
                     lambda:self.groups.rename(3,cid,'No'),lambda:self.groups.transfer(3,cid,self.ids[1])]:
            self.failure(404,call)
        self.failure(404,lambda:self.direct.messages(1,cid))
        dm=self.direct.direct(1,self.ids[2])['id']
        self.failure(404,lambda:self.groups.messages(1,dm))
        self.sql("UPDATE nova_profiles SET status='suspended' WHERE user_id=2")
        self.failure(404,lambda:self.send(cid,2))
        self.failure(404,lambda:self.groups.transfer(1,cid,self.ids[2]))
        self.groups.remove(1,cid,self.ids[2])

    def test_migration_idempotency_unique_owner(self):
        cid=self.create()
        db=self.connect()
        try:
            migrate_nova_groups(db,self.postgres)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE nova_chat_members SET role='owner' WHERE conversation_id=? AND user_id=2",(cid,))
            db.rollback()
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM nova_social_migrations').fetchone()['n'],3)
        finally:db.close()

    def test_validation_and_group_list(self):
        for name in ['', ' ', 'x'*81,'bad\x00name','\ud800',1]:
            self.failure(400,lambda:self.groups.create(1,name,[]))
        self.failure(400,lambda:self.groups.create(1,'Group',[self.ids[2],self.ids[2]]))
        self.failure(404,lambda:self.groups.create(1,'Group',[self.ids[1]]))
        first=self.create((2,));second=self.create(())
        page=self.groups.groups(1,limit=1)
        tail=self.groups.groups(1,cursor=page['next_cursor'],limit=1)
        self.assertEqual({g['id'] for g in page['groups']+tail['groups']},{first,second})
        self.failure(400,lambda:self.groups.groups(2,cursor=page['next_cursor']))
        self.failure(400,lambda:self.send(first,text=' '))
        self.failure(400,lambda:self.send(first,text='x'*4001))


class SQLiteGroupTests(GroupContract,unittest.TestCase):
    postgres=False

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'groups.db'
        db=self.connect();db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT)')
        for user in range(1,5):db.execute('INSERT INTO users VALUES(?,?)',(user,'Unchanged '+str(user)))
        db.commit();migrate_nova_profiles(db);db.close()
        self.prepare_groups()

    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def test_failed_migration_rolls_back(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)');db.commit()
        migrate_nova_profiles(db);migrate_nova_chat(db)
        db.execute('CREATE TABLE nova_chat_events(id INTEGER)');db.commit()
        with self.assertRaises(sqlite3.OperationalError):migrate_nova_groups(db)
        self.assertNotIn('name',[r['name'] for r in db.execute('PRAGMA table_info(nova_chat_conversations)').fetchall()])
        self.assertEqual(db.execute('SELECT COUNT(*) FROM nova_social_migrations').fetchone()[0],2)
        db.close()

    def test_concurrent_migration(self):
        def migrate(_):
            db=self.connect()
            try:migrate_nova_groups(db)
            finally:db.close()
        with ThreadPoolExecutor(3) as pool:list(pool.map(migrate,range(3)))


class GroupRouteTests(unittest.TestCase):
    setUp=SQLiteGroupTests.setUp
    connect=SQLiteGroupTests.connect
    prepare_groups=GroupContract.prepare_groups
    postgres=False

    def setup_routes(self):
        app=Flask(__name__);app.secret_key='synthetic-test'
        manager=LoginManager(app)
        class User(UserMixin):
            def __init__(self,user):self.id=user
        manager.user_loader(lambda user:User(user))
        def guard(name):
            f=open(Path(self.temp.name)/name,'a+');f.seek(0);return f
        self.guard=guard
        register_nova_chat(app,self.connect,guard)
        return app.test_client()

    def test_auth_csrf_api_and_free_access(self):
        client=self.setup_routes()
        routes=[('post',''),('get',''),('get','/invitations'),('get','/bad'),('patch','/bad'),
                ('post','/bad/members'),('post','/bad/join'),('post','/bad/leave'),
                ('delete','/bad/members/102'),('patch','/bad/members/102'),('post','/bad/ownership'),
                ('get','/bad/messages'),('post','/bad/messages'),('put','/bad/receipts'),('get','/bad/events')]
        prefix='/api/nova-chat/groups'
        for method,path in routes:
            result=getattr(client,method)(prefix+path)
            self.assertEqual(result.status_code,401)
            self.assertEqual(result.headers['Cache-Control'],'no-store')
        with client.session_transaction() as session:
            session['_user_id']='1';session['csrf_token']='synthetic'
        for method,path in routes:
            if method!='get':self.assertEqual(getattr(client,method)(prefix+path,json={}).status_code,403)
        headers={'X-CSRF-Token':'synthetic'}
        created=client.post(prefix,json={'name':'Group','member_ids':[self.ids[2]]},headers=headers)
        self.assertEqual(created.status_code,200)
        cid=created.json['group']['id']
        self.assertEqual(client.get(prefix+'/'+cid).status_code,200)
        sent=client.post(prefix+'/'+cid+'/messages',json={'type':'text','text':'Hello','client_message_id':str(uuid4())},headers=headers)
        self.assertEqual(sent.status_code,200)
        self.assertEqual(client.get(prefix+'/'+cid+'/messages').json['messages'][0]['text'],'Hello')
        self.assertEqual(client.post(prefix,json={'name':'x','member_ids':[],'user_id':2},headers=headers).status_code,400)
        self.assertEqual(client.post(prefix,json={'name':'x'*70000,'member_ids':[]},headers=headers).status_code,413)
        # Fixture deliberately contains no billing, subscription or AI-usage tables.

    def test_group_limits_and_shared_send_limit(self):
        self.setup_routes()
        limiter=ChatRateLimiter(self.guard)
        with patch('services.nova_chat_routes.time.time',return_value=1000):
            for _ in range(5):limiter('group_create',1)
        with patch('services.nova_chat_routes.time.time',return_value=5000):
            with self.assertRaises(ChatError):limiter('group_create',1)
        with patch('services.nova_chat_routes.time.time',return_value=87401):limiter('group_create',1)
        group=GroupChat(self.connect,rate_limit=limiter)
        direct=DirectChat(self.connect,rate_limit=limiter)
        cid=group.create(1,'Group',[])['id'];dm=direct.direct(1,self.ids[2])['id']
        for i in range(10):
            target,cid_to_send=(group,cid) if i%2 else (direct,dm)
            target.send(1,cid_to_send,{'type':'text','text':'test','client_message_id':str(uuid4())})
        with self.assertRaises(ChatError) as error:
            group.send(1,cid,{'type':'text','text':'limited','client_message_id':str(uuid4())})
        self.assertEqual(error.exception.status,429)


if __name__=='__main__':unittest.main()
