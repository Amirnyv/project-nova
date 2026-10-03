"""Native paper contract using real SQLite transactions and fake market quotes."""
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from flask_login import LoginManager, UserMixin
from services.paper_trading import PaperTrading, PaperError
from services.paper_routes import register_paper_trading
from services.paper_schema import initialize_paper_schema


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'paper.sqlite'
        self.now=1790951400.0
        self.quote={'symbol':'AAPL','name':'Apple','close':'100','timestamp':self.now,'is_market_open':True,'previous_close':'90'}
        self.service=PaperTrading(self.connect,quote=lambda s:dict(self.quote),clock=lambda:self.now)
        tree=ast.parse((Path(__file__).resolve().parents[1]/'database.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='init_sqlite_db')
        ns=dict(sqlite3=sqlite3,DB_PATH=self.path,get_db=self.connect)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'schema','exec'),ns)
        ns['init_sqlite_db']();initialize_paper_schema(self.connect)
        db=self.connect()
        db.executemany('INSERT INTO users(id,username,email,password_hash) VALUES(?,?,?,?)',[(1,'one','one@example.invalid','fake'),(2,'two','two@example.invalid','fake')]);db.commit();db.close()
        self.app=Flask('paper_test');self.app.secret_key='synthetic'
        manager=LoginManager(self.app)
        class User(UserMixin):
            def __init__(self,uid):self.id=uid
        manager.user_loader(lambda uid:User(uid))
        register_paper_trading(self.app,self.connect,quote=lambda s:dict(self.quote),clock=lambda:self.now)
        self.client=self.app.test_client()
        with self.client.session_transaction() as s:s['_user_id']='1';s['csrf_token']='test'

    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON');return db

    def preview(self,side='BUY',unit='shares',amount='1',uid=1):
        return self.service.preview(uid,dict(symbol='AAPL',side=side,unit=unit,amount=amount))

    def fill(self,**kwargs):return self.service.execute(kwargs.get('uid',1),self.preview(**kwargs)['preview_id'])

    def error(self,code,call):
        with self.assertRaises(PaperError) as raised:call()
        self.assertEqual(raised.exception.code,code)

    def test_first_portfolio_contract(self):
        p=self.service.portfolio(1)
        self.assertEqual(p['cash'],'10000.00');self.assertEqual(p['starting_cash'],'10000')
        self.assertTrue(p['simulation']);self.assertEqual(p['currency'],'USD')
        self.assertEqual(p['holdings'],[]);self.assertEqual(p['recent'],[])
        self.assertEqual(p['supported_symbols'],['SPY','QQQ','AAPL','TSLA','NVDA','AMZN','MSFT'])

    def test_buy_dollars_and_shares_fractional(self):
        a=self.fill(unit='dollars',amount='12.5');self.assertEqual(a['shares'],'0.125000')
        b=self.fill(amount='0.123456');self.assertEqual(b['total'],'12.35')
        p=self.service.portfolio(1);self.assertEqual(p['holdings'][0]['shares'],'0.248456')
        self.assertEqual(p['cash'],'9975.15')
        for k in ['cash','total','price','shares']:self.assertRegex(b[k],r'^\d+(\.\d+)?$')
        self.assertIsNotNone(datetime.fromisoformat(b['timestamp']).tzinfo)

    def test_sell_dollars_and_shares(self):
        self.fill(amount='2');self.quote['close']='110'
        p=self.preview(side='SELL',unit='dollars',amount='55');self.assertEqual(p['realized'],'5.00')
        self.service.execute(1,p['preview_id']);self.fill(side='SELL',amount='0.5')
        self.assertEqual(self.service.portfolio(1)['holdings'][0]['shares'],'1.000000')
        self.assertEqual(self.service.transactions(1)['transactions'][0]['realized'],'5.00')

    def test_insufficient_cash(self):self.error('insufficient_cash',lambda:self.preview(amount='101'))
    def test_insufficient_shares(self):self.error('insufficient_shares',lambda:self.preview(side='SELL'))
    def test_unsupported(self):self.error('unsupported_symbol',lambda:self.service.preview(1,dict(symbol='BTC/USD',side='BUY',unit='shares',amount='1')))

    def test_invalid_quantities(self):
        for amount in ['NaN','Infinity','-1','0','1e2','0.1234567','99999999999999999999999']:
            self.error('invalid_quantity',lambda:self.preview(amount=amount))

    def test_stale_and_unavailable_quote(self):
        self.quote['timestamp']=self.now-901;self.error('quote_unavailable',self.preview)
        self.quote.pop('timestamp');self.error('quote_unavailable',self.preview)
        self.assertEqual(self.service.portfolio(1)['day_gain'],'0.00')

    def test_day_gain_includes_todays_fills(self):
        self.fill(amount='2')
        self.quote['close']='110'
        self.fill(side='SELL',amount='1')
        self.assertEqual(self.service.portfolio(1)['day_gain'],'20.00')

    def test_missing_quote_holding_is_not_fabricated(self):
        self.fill()
        self.quote.pop('timestamp')
        p=self.service.portfolio(1)
        self.assertIsNone(p['total_value']);self.assertIsNone(p['holdings'][0]['price'])
        self.assertIsNone(p['day_gain'])

    def test_closed_market(self):
        self.quote['is_market_open']=False;self.error('quote_unavailable',self.preview)

    def test_expired(self):
        p=self.preview();self.now+=121;self.error('preview_expired',lambda:self.service.execute(1,p['preview_id']))

    def test_changed_quote_no_trade(self):
        p=self.preview();self.quote['close']='100.0001'
        self.error('quote_changed',lambda:self.service.execute(1,p['preview_id']))
        self.assertEqual(self.service.transactions(1)['transactions'],[])

    def test_duplicate_and_concurrent_execution(self):
        p=self.preview()
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:self.service.execute(1,p['preview_id']),range(4)))
        self.assertTrue(all(r==results[0] for r in results))
        self.now+=1000
        self.assertEqual(self.service.execute(1,p['preview_id']),results[0])
        self.assertEqual(len(self.service.transactions(1)['transactions']),1)

    def test_concurrent_overspend(self):
        previews=[self.preview(amount='75') for _ in range(2)]
        def run(p):
            try:return self.service.execute(1,p['preview_id'])
            except PaperError as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,previews))
        self.assertIn('insufficient_cash',results);self.assertEqual(self.service.portfolio(1)['cash'],'2500.00')

    def test_changed_preview_stays_invalid_after_price_returns(self):
        p=self.preview();self.quote['close']='101'
        self.error('quote_changed',lambda:self.service.execute(1,p['preview_id']))
        self.quote['close']='100'
        self.error('preview_unavailable',lambda:self.service.execute(1,p['preview_id']))

    def test_quote_error_does_not_expose_upstream_details(self):
        def broken(symbol):raise RuntimeError('https://example.invalid/quote?apikey=synthetic-secret')
        self.service.quote=broken
        with self.assertRaises(PaperError) as result:self.preview()
        self.assertNotIn('apikey',result.exception.message)
        self.assertNotIn('synthetic-secret',result.exception.message)

    def test_http_get_json_shapes(self):
        self.fill()
        p=self.client.get('/api/markets/paper/portfolio')
        self.assertEqual(p.status_code,200);self.assertEqual(p.mimetype,'application/json')
        self.assertEqual(p.headers['Cache-Control'],'no-store')
        holding=p.json['holdings'][0]
        self.assertTrue({'symbol','company','shares','average_price','cost_basis','price','value','gain','gain_percent','quote_at','quote_status'}<=set(holding))
        t=self.client.get('/api/markets/paper/transactions')
        self.assertEqual(t.status_code,200);self.assertIsInstance(t.json['transactions'][0]['id'],int)
        self.assertEqual(self.client.get('/api/markets/paper/transactions?before=bad').json['error'],'invalid_request')

    def test_legacy_rows_unchanged_by_additive_schema(self):
        db=self.connect()
        db.execute('INSERT INTO portfolios(user_id,cash) VALUES(1,9500)')
        db.execute("INSERT INTO positions(user_id,symbol,shares,average_price) VALUES(1,'AAPL',5,100)")
        db.execute("INSERT INTO trades(user_id,action,symbol,shares,price,total,created_at) VALUES(1,'BUY','AAPL',5,100,500,'2026-09-29 02:00:00 PM')")
        db.commit()
        before={t:[dict(r) for r in db.execute('SELECT * FROM '+t)] for t in ['portfolios','positions','trades']}
        initialize_paper_schema(self.connect)
        after={t:[dict(r) for r in db.execute('SELECT * FROM '+t)] for t in before}
        db.close();self.assertEqual(before,after)
        p=self.service.portfolio(1);self.assertEqual(p['cash'],'9500.00');self.assertIsNone(p['day_gain'])
        self.assertIsNotNone(datetime.fromisoformat(p['recent'][0]['timestamp']).tzinfo)

    def test_pagination(self):
        for _ in range(52):self.fill(amount='0.01')
        a=self.service.transactions(1);b=self.service.transactions(1,a['next_before'])
        self.assertEqual(len(a['transactions']),50);self.assertEqual(len(b['transactions']),2)
        self.assertFalse({r['id'] for r in a['transactions']} & {r['id'] for r in b['transactions']})
        self.assertIsNone(b['next_before'])

    def test_reset_invalidates_pending_and_keeps_duplicate_safe(self):
        p=self.preview();done=self.service.execute(1,p['preview_id']);pending=self.preview()
        self.assertEqual(self.service.reset(1),dict(simulation=True,cash='10000'))
        self.assertEqual(self.service.portfolio(1)['holdings'],[]);self.assertEqual(self.service.transactions(1)['transactions'],[])
        self.error('preview_unavailable',lambda:self.service.execute(1,pending['preview_id']))
        self.assertEqual(self.service.execute(1,p['preview_id']),done)
        self.assertEqual(self.service.portfolio(1)['cash'],'10000.00')

    def test_isolation(self):
        p=self.preview();self.error('preview_unavailable',lambda:self.service.execute(2,p['preview_id']))
        self.fill();self.service.reset(2)
        self.assertEqual(len(self.service.portfolio(1)['holdings']),1)
        self.assertEqual(self.service.transactions(2)['transactions'],[])

    def test_http_auth_csrf_errors_and_contract(self):
        anon=self.app.test_client()
        for route in ['portfolio','transactions']:
            r=anon.get('/api/markets/paper/'+route);self.assertEqual(r.status_code,401);self.assertEqual(r.json['error'],'unauthenticated')
        for route in ['preview','trades','reset']:
            r=self.client.post('/api/markets/paper/'+route,json={});self.assertEqual(r.status_code,403);self.assertEqual(r.json['error'],'csrf_failed')
        headers={'X-CSRF-Token':'test'}
        r=self.client.post('/api/markets/paper/preview',json=dict(symbol='AAPL',side='BUY',unit='shares',amount='1'),headers=headers)
        self.assertEqual(r.status_code,200);self.assertIsInstance(r.json['expires_at'],(float,int))
        r=self.client.post('/api/markets/paper/trades',json={'preview_id':r.json['preview_id']},headers=headers)
        self.assertEqual(r.status_code,200);self.assertIsInstance(r.json['transaction_id'],int)
        r=self.client.post('/api/markets/paper/reset',json={'confirmation':'wrong'},headers=headers)
        self.assertEqual(r.json['error'],'confirmation_required')
        r=self.client.post('/api/markets/paper/reset',json={'confirmation':'RESET PAPER PORTFOLIO'},headers=headers)
        self.assertEqual(r.json,{'simulation':True,'cash':'10000'})
        r=self.client.post('/api/markets/paper/preview',json={'amount':1},headers=headers)
        self.assertEqual(set(r.json),{'error','message'});self.assertEqual(r.json['error'],'invalid_request')

    def test_repeated_schema_preserves_chat_data(self):
        from agents import portfolio_agent
        with patch.object(portfolio_agent,'get_db',self.connect),patch('database.USE_POSTGRES',False):
            buy=portfolio_agent.buy_stock(1,'AAPL',2,100)
            self.assertTrue(buy['success']);self.assertEqual(buy['cost'],200)
            initialize_paper_schema(self.connect);initialize_paper_schema(self.connect)
            self.assertEqual(self.service.portfolio(1)['holdings'][0]['shares'],'2.000000')
            self.fill(side='SELL',amount='1')
            self.assertEqual(portfolio_agent.get_portfolio(1)['positions']['AAPL']['shares'],1)
            self.assertTrue(portfolio_agent.sell_stock(1,'AAPL',1,110)['success'])
            self.assertEqual(len(portfolio_agent.get_trade_history(1)),3)
