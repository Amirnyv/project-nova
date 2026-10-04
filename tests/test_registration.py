"""Signup adapters isolated from app startup, secrets, providers and production DB."""
import ast
import fcntl
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import Mock
from flask import Flask, jsonify, request, session, flash, redirect, url_for, render_template
from flask_login import LoginManager, current_user, login_user, UserMixin
from werkzeug.security import check_password_hash
from services.registration import create_account, RegistrationError


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.db'
        db=self.connect();db.executescript('''CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE, password_hash TEXT);
        CREATE TABLE portfolios(id INTEGER PRIMARY KEY,user_id INTEGER UNIQUE,cash REAL);''');db.close()
        root=Path(__file__).resolve().parents[1]
        app=Flask('signup_test',template_folder=str(root/'templates'));app.secret_key='synthetic-only'
        manager=LoginManager(app)
        class User(UserMixin):
            def __init__(self,uid,username='',email=''):self.id=str(uid);self.username=username;self.email=email
        manager.user_loader(lambda uid:User(uid))
        app.add_url_rule('/app','home',lambda:jsonify(authenticated=current_user.is_authenticated))
        app.add_url_rule('/login','login',lambda:'Login')
        self.email=Mock()
        def guard(name):
            handle=open(Path(self.temp.name)/(name+'.json'),'a+')
            handle.seek(0)
            return handle
        # a+ writes append; seek/truncate used by production guard remain valid.
        ns=dict(app=app,current_user=current_user,request=request,session=session,jsonify=jsonify,
                flash=flash,redirect=redirect,url_for=url_for,render_template=render_template,
                secrets=secrets,hmac=hmac,hashlib=hashlib,json=json,time=time,fcntl=fcntl,
                local_guard_file=guard,create_account=create_account,RegistrationError=RegistrationError,
                get_db=self.connect,User=User,login_user=login_user,send_welcome_email=self.email)
        names={'csrf_token','csrf_context','protect_browser_mutations','limit_auth_requests','complete_registration','signup','api_csrf','api_signup'}
        nodes=[n for n in ast.parse((root/'app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'isolated_signup','exec'),ns)
        self.app=app;self.client=app.test_client()
        self.token=self.client.get('/api/auth/csrf').json['csrf_token']
        self.data=dict(username=' Alice ',email=' ALICE@EXAMPLE.COM ',password='synthetic-password',confirm_password='synthetic-password')

    def connect(self):
        db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row;return db

    def post(self,data=None,web=False):
        return self.client.post('/signup' if web else '/api/auth/signup',
            **({'data':data or self.data} if web else {'json':data or self.data}),headers={'X-CSRF-Token':self.token})

    def test_api_success_session_hash_and_portfolio(self):
        r=self.post();self.assertEqual(r.status_code,201);self.assertEqual(r.json['user']['username'],'Alice')
        self.assertEqual(r.json['user']['email'],'alice@example.com')
        self.assertTrue(self.client.get('/app').json['authenticated'])
        db=self.connect()
        row=db.execute('SELECT * FROM users').fetchone()
        self.assertTrue(check_password_hash(row['password_hash'],self.data['password']))
        self.assertEqual(db.execute('SELECT cash FROM portfolios').fetchone()['cash'],10000)
        db.close();self.email.assert_called_once_with('alice@example.com','Alice')

    def test_web_form_and_success(self):
        self.assertIn(b'name="csrf_token"',self.client.get('/signup').data)
        r=self.post(web=True);self.assertEqual(r.status_code,302);self.assertEqual(r.location,'/app')
        self.email.assert_called_once()

    def test_csrf_bootstrap_reuses_cookie_and_rejects_missing_header(self):
        r=self.client.get('/api/auth/csrf');self.assertEqual(r.json['csrf_token'],self.token)
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertEqual(self.client.post('/api/auth/signup',json=self.data).status_code,403)
        self.assertEqual(self.app.test_client().post('/api/auth/signup',json=self.data,headers={'X-CSRF-Token':self.token}).status_code,403)
        self.email.assert_not_called()

    def test_shared_validation(self):
        for values in [dict(email='invalid'),dict(password='short',confirm_password='short'),dict(confirm_password='different'),dict(username='x'*81),dict(password='x'*257,confirm_password='x'*257)]:
            data={**self.data,**values}
            with self.assertRaises(RegistrationError):create_account(self.connect,*(data[k] for k in ['username','email','password','confirm_password']))
        r=self.post({**self.data,'email':'invalid'});self.assertEqual(r.status_code,400)
        r=self.post({**self.data,'email':'invalid'},web=True);self.assertEqual(r.status_code,200);self.assertIn(b'valid email',r.data)

    def test_duplicate_email_and_username(self):
        create_account(self.connect,'Alice','alice@example.com','synthetic-password','synthetic-password')
        for data in [{**self.data,'username':'Bob'},{**self.data,'email':'other@example.com'}]:
            self.assertEqual(self.post(data).status_code,409)
        self.email.assert_not_called()
        db=self.connect();self.assertEqual(db.execute('SELECT COUNT(*) FROM portfolios').fetchone()[0],1);db.close()

    def test_welcome_failure_preserves_signup(self):
        self.email.side_effect=RuntimeError('synthetic provider failure')
        self.assertEqual(self.post().status_code,201)
        self.assertTrue(self.client.get('/app').json['authenticated']);self.email.assert_called_once()

    def test_shared_email_rate_limit_between_adapters(self):
        data={**self.data,'password':'short','confirm_password':'short'}
        for i in range(5):self.assertIn(self.post(data,web=i%2==0).status_code,[200,400])
        r=self.post(data);self.assertEqual(r.status_code,429);self.assertEqual(r.json['error'],'rate_limited')
        self.assertIn('Retry-After',r.headers)
        self.assertEqual(self.post(data,web=True).status_code,429)

    def test_shared_ip_rate_limit(self):
        for i in range(20):
            r=self.post({**self.data,'email':f'u{i}@example.com','password':'short','confirm_password':'short'},web=i%2==0)
            self.assertIn(r.status_code,[200,400])
        self.assertEqual(self.post().status_code,429)

    def test_real_transaction_does_not_leave_orphan_user(self):
        db=self.connect()
        db.execute("CREATE TRIGGER reject_portfolio BEFORE INSERT ON portfolios BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        db.commit();db.close()
        with self.assertRaises(RegistrationError):
            create_account(self.connect,'Alice','alice@example.com','synthetic-password','synthetic-password')
        db=self.connect();self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],0);db.close()

    def test_malformed_json_and_wrong_field_types(self):
        for data in [[], {'username': 'Alice'}, {**self.data, 'email': ['not-string']}]:
            response=self.client.post('/api/auth/signup',json=data,headers={'X-CSRF-Token':self.token})
            self.assertEqual(response.status_code,400)
            self.assertIn('error',response.json)
        self.email.assert_not_called()

    def test_transaction_rollback_and_connection_cleanup(self):
        class Broken:
            closed=False;rolled_back=False
            def execute(self,sql,args):
                if 'portfolios' in sql:raise RuntimeError('synthetic insert failure')
                return type('Cursor',(),{'lastrowid':1})()
            def rollback(self):self.rolled_back=True
            def close(self):self.closed=True
        db=Broken()
        with self.assertRaises(RuntimeError):create_account(lambda:db,'Alice','alice@example.com','synthetic-password','synthetic-password')
        self.assertTrue(db.closed);self.assertTrue(db.rolled_back)
