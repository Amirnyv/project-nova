"""SQLite and shared PostgreSQL direct-message contract tests; no app import."""
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
from services.nova_chat_schema import migrate_nova_chat
from services.nova_profile_schema import migrate_nova_profiles
from services.nova_profiles import claim_profile


class MessagingContract:
    def prepare(self):
        self.profile_ids = {}
        for uid, handle in [(1,'alice'),(2,'bobby'),(3,'carol'),(4,'david')]:
            result=claim_profile(self.connect,uid,handle,postgres=self.postgres,discoverable=True)
            # Public profile identifiers must not be confused with account IDs.
            public=int(result['id'])+100
            db=self.connect()
            db.execute('UPDATE nova_profiles SET id=? WHERE user_id=?',(public,uid))
            db.commit();db.close()
            self.profile_ids[uid]=str(public)
        db=self.connect()
        migrate_nova_chat(db,self.postgres)
        db.close()
        self.chat=DirectChat(self.connect,self.postgres)

    def dm(self,a=1,b=2):
        return self.chat.direct(a,self.profile_ids[b])['id']

    def send(self,cid,user=1,text='Hello',client_id=None,kind='text'):
        return self.chat.send(user,cid,{'client_message_id':client_id or str(uuid4()),'type':kind,'text':text})

    def error(self,status,operation):
        with self.assertRaises(ChatError) as raised: operation()
        self.assertEqual(raised.exception.status,status)
        return raised.exception.code

    def execute(self,sql,params=()):
        db=self.connect()
        try:
            result=db.execute(sql,params)
            db.commit()
            return result
        finally: db.close()

    def test_pair_reuse_and_self(self):
        cid=self.dm()
        self.assertEqual(cid,self.dm())
        self.assertEqual(cid,self.dm(2,1))
        self.error(400,lambda:self.dm(1,1))
        self.error(404,lambda:self.chat.direct(1,'99999'))

    def test_concurrent_creation(self):
        with ThreadPoolExecutor(4) as executor:
            ids=list(executor.map(lambda i:self.dm(1,2) if i%2 else self.dm(2,1),range(8)))
        self.assertEqual(len(set(ids)),1)

    def test_sends_order_and_retries(self):
        cid=self.dm(); key=str(uuid4())
        first=self.send(cid,client_id=key)
        self.assertEqual(first,self.send(cid,client_id=key))
        self.error(409,lambda:self.send(cid,text='Different',client_id=key))
        self.error(409,lambda:self.send(cid,client_id=key,kind='location'))
        second=self.send(cid,user=2,client_id=key)
        self.assertEqual([first['seq'],second['seq']],[1,2])
        self.assertEqual(self.chat.messages(1,cid)['messages'],[first,second])

    def test_simultaneous_sends(self):
        cid=self.dm()
        with ThreadPoolExecutor(4) as executor:
            messages=list(executor.map(lambda i:self.send(cid,1 if i%2 else 2,text=str(i)),range(12)))
        self.assertEqual(sorted(m['seq'] for m in messages),list(range(1,13)))
        key=str(uuid4())
        with ThreadPoolExecutor(3) as executor:
            retries=list(executor.map(lambda _:self.send(cid,client_id=key),range(3)))
        self.assertEqual(len({m['id'] for m in retries}),1)

    def test_invalid_messages(self):
        cid=self.dm()
        for text in ['', '   ', 'x'*4001, '\x00', '\ud800', 12, {}]:
            self.error(400,lambda:self.send(cid,text=text))
        self.error(400,lambda:self.send(cid,kind='location'))
        self.error(400,lambda:self.send(cid,client_id='not-a-uuid'))
        self.assertEqual(self.send(cid,text='😀'*4000)['seq'],1)

    def test_idor(self):
        cid=self.dm(); self.send(cid)
        for operation in [lambda:self.chat.conversation(3,cid),lambda:self.chat.messages(3,cid),
                          lambda:self.send(cid,user=3),lambda:self.chat.receipts(3,cid,{'read_through_seq':1})]:
            self.error(404,operation)
        self.assertEqual(self.error(404,lambda:self.chat.conversation(3,cid)),
                         self.error(404,lambda:self.chat.conversation(3,str(uuid4()))))
        self.error(400,lambda:self.chat.conversation(1,'bad'))

    def test_message_pages(self):
        cid=self.dm()
        for i in range(7): self.send(cid,text=str(i))
        page=self.chat.messages(2,cid,limit=3)
        self.assertEqual([m['seq'] for m in page['messages']],[5,6,7])
        older=self.chat.messages(2,cid,cursor=page['next_cursor'],limit=3)
        self.assertEqual([m['seq'] for m in older['messages']],[2,3,4])
        oldest=self.chat.messages(2,cid,cursor=older['next_cursor'],limit=3)
        self.assertEqual([m['seq'] for m in oldest['messages']],[1])
        self.assertFalse(oldest['has_more'])
        self.assertIsNone(oldest['next_cursor'])
        self.error(400,lambda:self.chat.messages(1,cid,cursor='invalid'))
        self.error(400,lambda:self.chat.messages(1,cid,cursor=encode_cursor({'scope':'messages:'+str(uuid4()),'before':4})))
        self.error(400,lambda:self.chat.messages(1,cid,limit=101))
        self.assertEqual(len(self.chat.messages(1,cid,limit=100)['messages']),7)

    def test_conversation_pages(self):
        for other in [2,3,4]: self.dm(1,other)
        page=self.chat.conversations(1,limit=2)
        tail=self.chat.conversations(1,cursor=page['next_cursor'],limit=2)
        self.assertEqual(len(page['conversations']),2)
        self.assertEqual(len(tail['conversations']),1)
        self.assertEqual(len({c['id'] for c in page['conversations']+tail['conversations']}),3)
        self.error(400,lambda:self.chat.conversations(2,cursor=page['next_cursor']))
        from services.nova_chat import decode_cursor
        decode_cursor(page['next_cursor'],'list:profile:'+self.profile_ids[1])

    def test_receipts_unread(self):
        cid=self.dm(); self.send(cid); self.send(cid); self.send(cid,user=2)
        self.assertEqual(self.chat.conversation(2,cid)['unread_count'],2)
        self.assertEqual(self.chat.receipts(2,cid,{'delivered_through_seq':1})['last_delivered_seq'],1)
        result=self.chat.receipts(2,cid,{'read_through_seq':2})
        self.assertEqual(result,{'last_read_seq':2,'last_delivered_seq':2})
        self.assertEqual(self.chat.receipts(2,cid,{'read_through_seq':0,'delivered_through_seq':0}),result)
        self.error(400,lambda:self.chat.receipts(2,cid,{'read_through_seq':4}))
        self.error(400,lambda:self.chat.receipts(2,cid,{'read_through_seq':True}))
        self.error(400,lambda:self.chat.receipts(2,cid,{'read_through_seq':1,'user_id':1}))
        self.assertEqual(self.chat.conversation(1,cid)['last_read_seq'],0)
        self.assertEqual(self.chat.conversation(2,cid)['unread_count'],0)

    def test_blocks_private_idempotent(self):
        cid=self.dm()
        self.chat.block(1,self.profile_ids[2]);self.chat.block(1,self.profile_ids[2])
        self.assertEqual(len(self.chat.blocks(1)['blocks']),1)
        self.assertEqual(self.chat.blocks(2)['blocks'],[])
        self.error(404,lambda:self.send(cid))
        self.error(404,lambda:self.send(cid,user=2))
        self.error(404,lambda:self.dm())
        self.error(404,lambda:self.dm(2,1))
        self.chat.block(1,self.profile_ids[3])
        self.error(404,lambda:self.dm(1,3))
        self.error(400,lambda:self.chat.block(1,self.profile_ids[1]))
        self.chat.block(1,self.profile_ids[2],remove=True)
        self.assertEqual(self.send(cid)['seq'],1)

    def test_send_block_race(self):
        cid=self.dm()
        def race_send():
            try: return self.send(cid)
            except ChatError as error: self.assertEqual(error.status,404)
        with ThreadPoolExecutor(2) as executor:
            send=executor.submit(race_send)
            block=executor.submit(self.chat.block,2,self.profile_ids[1])
            send.result();block.result()
        self.error(404,lambda:self.send(cid))
        self.error(404,lambda:self.dm())

    def test_discovery_privacy(self):
        self.assertEqual(self.chat.search(1,'BoB')['users'][0]['handle'],'bobby')
        self.assertEqual(self.chat.search(1,'alice')['users'],[])
        self.execute('UPDATE nova_profiles SET discoverable=0 WHERE user_id=2')
        self.assertEqual(self.chat.search(1,'bob')['users'],[])
        self.error(404,lambda:self.dm())
        self.execute("UPDATE nova_profiles SET discoverable=1,status='suspended' WHERE user_id=2")
        self.assertEqual(self.chat.search(1,'bob')['users'],[])
        self.execute("UPDATE nova_profiles SET status='active' WHERE user_id=2")
        self.chat.block(2,self.profile_ids[1])
        self.assertEqual(self.chat.search(1,'bob')['users'],[])
        self.error(400,lambda:self.chat.search(1,'bo'))
        self.error(400,lambda:self.chat.search(1,"%' OR 1=1"))

    def test_suspended_senders_and_recipients(self):
        cid=self.dm();self.send(cid)
        for status in ['suspended','deactivated']:
            self.execute('UPDATE nova_profiles SET status=? WHERE user_id=1',(status,))
            self.error(404,lambda:self.send(cid))
            self.error(404,lambda:self.send(cid,user=2))
        self.execute("UPDATE nova_profiles SET status='active' WHERE user_id=1")
        self.assertEqual(len(self.chat.messages(1,cid)['messages']),1)

    def test_no_private_serialization(self):
        cid=self.dm(); self.send(cid)
        payload=json.dumps(self.chat.conversation(1,cid))
        for key in ['user_id','sender_id','creator_id','direct_low','direct_high','password_hash','email']:
            self.assertNotIn('"'+key+'"',payload)

    def test_constraints_and_rerun(self):
        cid=self.dm()
        db=self.connect()
        try:
            migrate_nova_chat(db,self.postgres)
            for sql,params in [
                ('INSERT INTO nova_chat_blocks(blocker_id,blocked_id,created_at) VALUES(1,1,?)',('2026-01-01T00:00:00+00:00',)),
                ('INSERT INTO nova_chat_blocks(blocker_id,blocked_id,created_at) VALUES(1,99999,?)',('2026-01-01T00:00:00+00:00',)),
                ('UPDATE nova_chat_members SET last_read_seq=5 WHERE conversation_id=?',(cid,)),
                ('UPDATE nova_chat_conversations SET direct_low=direct_high WHERE id=?',(cid,))]:
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql,params)
                db.rollback()
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM nova_social_migrations').fetchone()['n'],2)
        finally:db.close()


class SQLiteMessagingTests(MessagingContract,unittest.TestCase):
    postgres=False

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'chat.db'
        db=self.connect()
        db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT)')
        for uid in range(1,5): db.execute('INSERT INTO users VALUES(?,?)',(uid,'Existing '+str(uid)))
        db.commit();migrate_nova_profiles(db);db.close()
        self.prepare()

    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def test_concurrent_migration(self):
        def migrate(_):
            db=self.connect()
            try:migrate_nova_chat(db)
            finally:db.close()
        with ThreadPoolExecutor(3) as executor:list(executor.map(migrate,range(3)))

    def test_rollback_partial_migration(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)');db.commit()
        migrate_nova_profiles(db)
        db.execute('CREATE TABLE nova_chat_blocks(id INTEGER)');db.commit()
        with self.assertRaises(sqlite3.OperationalError):migrate_nova_chat(db)
        self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='nova_chat_messages'").fetchone())
        self.assertEqual(db.execute('SELECT COUNT(*) FROM nova_social_migrations').fetchone()[0],1)
        db.close()


class RouteTests(SQLiteMessagingTests):
    def setUp(self):
        super().setUp()
        self.app=Flask(__name__);self.app.secret_key='synthetic'
        manager=LoginManager(self.app)
        class User(UserMixin):
            def __init__(self,uid):self.id=uid
        manager.user_loader(lambda uid:User(uid))
        def guard(name):
            handle=open(Path(self.temp.name)/name,'a+');handle.seek(0);return handle
        self.guard=guard
        register_nova_chat(self.app,self.connect,guard)
        self.client=self.app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session['_user_id']='1';session['csrf_token']='synthetic-csrf'

    def test_auth_csrf_free_and_private(self):
        cid=self.dm()
        routes=[('post','/conversations/direct'),('get','/conversations'),('get','/conversations/'+cid),
                ('get','/conversations/'+cid+'/messages'),('post','/conversations/'+cid+'/messages'),
                ('put','/conversations/'+cid+'/receipts'),('get','/blocks'),('put','/blocks/2'),('delete','/blocks/2'),('get','/users')]
        for method,path in routes:
            response=getattr(self.client,method)('/api/nova-chat'+path)
            self.assertEqual(response.status_code,401)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.login()
        for method,path in routes:
            if method!='get': self.assertEqual(getattr(self.client,method)('/api/nova-chat'+path,json={}).status_code,403)
        response=self.client.post('/api/nova-chat/conversations/direct',json={'recipient_id':self.profile_ids[2]},headers={'X-CSRF-Token':'synthetic-csrf'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['conversation']['id'],cid)
        # No subscription/AI tables exist in the SQLite fixture.
        self.assertEqual(self.client.get('/api/nova-chat/conversations').status_code,200)

    def test_limits_and_retry_exemption(self):
        self.login();cid=self.dm();headers={'X-CSRF-Token':'synthetic-csrf'}
        url='/api/nova-chat/conversations/'+cid+'/messages'
        first=None
        for i in range(10):
            data={'client_message_id':str(uuid4()),'type':'text','text':str(i)}
            if first is None:first=data
            self.assertEqual(self.client.post(url,json=data,headers=headers).status_code,200)
        self.assertEqual(self.client.post(url,json={'client_message_id':str(uuid4()),'type':'text','text':'too fast'},headers=headers).status_code,429)
        self.assertEqual(self.client.post(url,json=first,headers=headers).status_code,200)
        self.assertEqual(self.client.post(url,json={'x':'a'*70000},headers=headers).status_code,413)
        for _ in range(30):self.assertEqual(self.client.get('/api/nova-chat/users?username=bob').status_code,200)
        self.assertEqual(self.client.get('/api/nova-chat/users?username=bob').status_code,429)

    def test_rate_windows_and_creation(self):
        limiter=ChatRateLimiter(self.guard)
        with patch('services.nova_chat_routes.time.time',return_value=1000):
            for _ in range(20):limiter('create',1)
            self.error(429,lambda:limiter('create',1))
        with patch('services.nova_chat_routes.time.time',return_value=4601):limiter('create',1)
        for batch in range(6):
            with patch('services.nova_chat_routes.time.time',return_value=5000+batch*10):
                for _ in range(10):limiter('send',1)
        with patch('services.nova_chat_routes.time.time',return_value=5059):self.error(429,lambda:limiter('send',1))
        with patch('services.nova_chat_routes.time.time',return_value=5061):limiter('send',1)

    def test_api_workflow_and_read_only_gets(self):
        self.login()
        headers={'X-CSRF-Token':'synthetic-csrf'}
        prefix='/api/nova-chat'
        response=self.client.post(prefix+'/conversations/direct',json={'recipient_id':self.profile_ids[2]},headers=headers)
        cid=response.json['conversation']['id']
        url=prefix+'/conversations/'+cid
        data={'client_message_id':str(uuid4()),'type':'text','text':'API message'}
        sent=self.client.post(url+'/messages',json=data,headers=headers)
        self.assertEqual(sent.status_code,200)
        self.assertEqual(self.client.get(url+'/messages').json['messages'][0],sent.json['message'])
        self.assertEqual(self.client.get(url).json['conversation']['last_read_seq'],0)
        receipt=self.client.put(url+'/receipts',json={'read_through_seq':1},headers=headers)
        self.assertEqual(receipt.json['last_delivered_seq'],1)
        block_url=prefix+'/blocks/'+self.profile_ids[2]
        self.assertEqual(self.client.put(block_url,headers=headers).status_code,200)
        self.assertEqual(self.client.get(prefix+'/blocks').json['blocks'][0]['id'],self.profile_ids[2])
        self.assertEqual(self.client.delete(block_url,headers=headers).status_code,200)
        self.assertEqual(self.client.get(prefix+'/blocks').json['blocks'],[])
        self.assertEqual(self.client.post(prefix+'/conversations/direct',json={'recipient_id':'9999999999'},headers=headers).status_code,400)


if __name__=='__main__':unittest.main()
