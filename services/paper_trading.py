"""Virtual USD trading only. No brokerage clients or real order execution."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
import json
import re
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

SYMBOLS = ('SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'AMZN', 'MSFT')
CENT = Decimal('.01')
SHARE = Decimal('.000001')
NY = ZoneInfo('America/New_York')


class PaperError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


def dec(value):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or abs(n) > Decimal('1000000000000'):
            raise ValueError()
        return n
    except (InvalidOperation, ValueError, TypeError):
        raise PaperError('invalid_quantity', 'Enter a valid positive quantity.') from None


def money(n):
    return n.quantize(CENT, rounding=ROUND_HALF_UP)


def text(n):
    return format(n, 'f')


def iso(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            value = datetime.strptime(value, '%Y-%m-%d %I:%M:%S %p')
    # Historical chat timestamps used naive server time (assumed UTC).
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()


def market_quote(symbol):
    # Raw timestamp is required: the legacy UI quote intentionally omits it.
    from agents.stock_agent import get_json
    return get_json('quote', {'symbol': symbol})


class PaperTrading:
    def __init__(self, factory, postgres=False, quote=market_quote, clock=time.time):
        self.factory, self.postgres, self.quote, self.clock = factory, postgres, quote, clock

    @contextmanager
    def locked(self, uid):
        db = self.factory()
        try:
            if self.postgres:
                db.execute("SET LOCAL lock_timeout = '5s'")
                db.execute('SELECT id FROM users WHERE id=? FOR UPDATE', (uid,))
            else:
                db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO portfolios(user_id,cash) VALUES(?,10000) ON CONFLICT(user_id) DO NOTHING', (uid,))
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def quote_data(self, symbol, fill=False):
        try:
            q = self.quote(symbol)
            price = dec(q['close'])
            at = float(q['timestamp'])
            if q.get('symbol') != symbol or price <= 0 or not 0 <= self.clock() - at <= 900:
                raise ValueError()
            if fill and q.get('is_market_open') is not True:
                raise ValueError()
            return q, price, datetime.fromtimestamp(at, timezone.utc).isoformat()
        except Exception:
            raise PaperError('quote_unavailable', 'A recent market quote is unavailable. Try again during market hours.', 503) from None

    def state(self, db, uid, symbol):
        cash = dec(db.execute('SELECT cash FROM portfolios WHERE user_id=?', (uid,)).fetchone()['cash'])
        row = db.execute('SELECT shares,average_price FROM positions WHERE user_id=? AND symbol=?', (uid,symbol)).fetchone()
        return money(cash), dec(row['shares']).quantize(SHARE) if row else Decimal(0), dec(row['average_price']) if row else Decimal(0)

    def calculate(self, db, uid, symbol, side, shares, price):
        cash, owned, average = self.state(db, uid, symbol)
        total = money(shares * price)
        if shares <= 0 or total <= 0:
            raise PaperError('invalid_quantity', 'The trade must be at least one cent.')
        if side == 'BUY' and total > cash:
            raise PaperError('insufficient_cash', 'Not enough simulated cash.')
        if side == 'SELL' and shares > owned:
            raise PaperError('insufficient_shares', 'Not enough simulated shares.')
        return dict(remaining_cash=text(cash-total if side=='BUY' else cash+total),
                    remaining_shares=text(owned+shares if side=='BUY' else owned-shares),
                    realized=text(money(total-shares*average) if side=='SELL' else Decimal(0)), total=text(total))

    def preview(self, uid, data):
        if set(data) != {'symbol','side','unit','amount'} or not all(isinstance(v,str) for v in data.values()):
            raise PaperError('invalid_request', 'Provide symbol, side, unit and amount.')
        symbol, side, unit = data['symbol'], data['side'], data['unit']
        if symbol not in SYMBOLS:
            raise PaperError('unsupported_symbol', 'This symbol is not available for simulated trading.')
        if side not in ('BUY','SELL') or unit not in ('dollars','shares'):
            raise PaperError('invalid_request', 'Choose BUY or SELL and dollars or shares.')
        if not re.fullmatch(r'\d{1,12}(?:\.\d{1,6})?',data['amount']):
            raise PaperError('invalid_quantity', 'Use a positive decimal with at most six decimal places.')
        amount = dec(data['amount'])
        if amount <= 0:
            raise PaperError('invalid_quantity', 'Amount must be positive.')
        q, price, at = self.quote_data(symbol, True)
        shares = (amount.quantize(CENT, rounding=ROUND_DOWN) / price).quantize(SHARE, rounding=ROUND_DOWN) if unit=='dollars' else amount.quantize(SHARE)
        with self.locked(uid) as db:
            result = self.calculate(db,uid,symbol,side,shares,price)
            result.update(preview_id=uuid4().hex, expires_at=self.clock()+120, symbol=symbol,
                          company=str(q.get('name') or symbol), side=side, shares=text(shares),price=text(price),quote_at=at)
            db.execute('DELETE FROM paper_previews WHERE user_id=? AND result IS NULL AND expires_at<?', (uid,self.clock()))
            db.execute('INSERT INTO paper_previews(preview_id,user_id,expires_at,payload) VALUES(?,?,?,?)',
                       (result['preview_id'],uid,result['expires_at'],json.dumps(result)))
            return result

    def write_trade(self, db, uid, symbol, side, shares, price):
        result = self.calculate(db,uid,symbol,side,shares,price)
        _, owned, average = self.state(db,uid,symbol)
        remaining = dec(result['remaining_shares'])
        if remaining == 0:
            db.execute('DELETE FROM positions WHERE user_id=? AND symbol=?',(uid,symbol))
        else:
            average = ((owned*average+shares*price)/remaining).quantize(Decimal('.00000001')) if side=='BUY' else average
            db.execute('''INSERT INTO positions(user_id,symbol,shares,average_price) VALUES(?,?,?,?)
                ON CONFLICT(user_id,symbol) DO UPDATE SET shares=excluded.shares,average_price=excluded.average_price''',
                (uid,symbol,float(remaining),float(average)))
        db.execute('UPDATE portfolios SET cash=? WHERE user_id=?',(float(dec(result['remaining_cash'])),uid))
        stamp = datetime.fromtimestamp(self.clock(),timezone.utc).isoformat()
        tx = db.execute('INSERT INTO trades(user_id,action,symbol,shares,price,total,created_at) VALUES(?,?,?,?,?,?,?)',
                        (uid,side,symbol,float(shares),float(price),float(dec(result['total'])),stamp))
        tid = tx.lastrowid
        db.execute('INSERT INTO paper_trade_details(trade_id,user_id,realized) VALUES(?,?,?)',(tid,uid,result['realized']))
        return dict(transaction_id=tid,side=side,symbol=symbol,shares=text(shares),price=text(price),
                    total=result['total'],timestamp=stamp,cash=result['remaining_cash'])

    def execute(self, uid, preview_id):
        if not isinstance(preview_id,str) or not re.fullmatch('[a-f0-9]{32}',preview_id):
            raise PaperError('preview_unavailable','Review a new trade first.',409)
        # Lock covers validation, quote recheck, balance mutation and persisted result.
        with self.locked(uid) as db:
            row = db.execute('SELECT * FROM paper_previews WHERE preview_id=? AND user_id=?',(preview_id,uid)).fetchone()
            if not row or row['invalidated']:
                raise PaperError('preview_unavailable','Review a new trade first.',409)
            if row['result']:
                return json.loads(row['result'])
            if row['expires_at'] <= self.clock():
                raise PaperError('preview_expired','This preview expired. Review a new trade.',409)
            p = json.loads(row['payload'])
            _, price, _ = self.quote_data(p['symbol'],True)
            if price != dec(p['price']):
                db.execute('UPDATE paper_previews SET invalidated=1 WHERE preview_id=?',(preview_id,))
                db.commit()
                raise PaperError('quote_changed','The price changed. Review a new trade.',409)
            if row['expires_at'] <= self.clock():
                raise PaperError('preview_expired','This preview expired. Review a new trade.',409)
            result = self.write_trade(db,uid,p['symbol'],p['side'],dec(p['shares']),price)
            db.execute('UPDATE paper_previews SET result=? WHERE preview_id=?',(json.dumps(result),preview_id))
            return result

    def legacy_trade(self, uid, symbol, shares, price, side):
        shares,price=dec(shares).quantize(SHARE),dec(price)
        if shares <= 0 or price <= 0:
            raise PaperError('invalid_quantity','Shares and price must be positive.')
        with self.locked(uid) as db:
            return self.write_trade(db,uid,symbol.upper(),side,shares,price)

    def history(self, db, uid):
        rows=db.execute('''SELECT t.*, d.realized AS stored_realized FROM trades t
            LEFT JOIN paper_trade_details d ON d.trade_id=t.id AND d.user_id=t.user_id
            WHERE t.user_id=? ORDER BY t.id''',(uid,)).fetchall()
        positions={}; result=[]
        for r in rows:
            shares,price,total=dec(r['shares']),dec(r['price']),dec(r['total'])
            owned,average=positions.get(r['symbol'],(Decimal(0),Decimal(0)))
            realized=dec(r['stored_realized']) if r['stored_realized'] is not None else (money(total-shares*average) if r['action']=='SELL' else Decimal(0))
            if r['action']=='BUY':
                average=(owned*average+shares*price)/(owned+shares)
                if r['stored_realized'] is None:average=money(average)
                owned+=shares
            else:owned-=shares
            positions[r['symbol']]=(owned,average)
            result.append(dict(id=r['id'],side=r['action'],symbol=r['symbol'],shares=text(shares.quantize(SHARE)),
                               price=text(price),total=text(money(total)),realized=text(realized),timestamp=iso(r['created_at'])))
        return result

    def transactions(self, uid, before=None):
        if before is not None and (not re.fullmatch(r'[1-9]\d{0,18}',str(before))):
            raise PaperError('invalid_request','Invalid transaction cursor.')
        with self.locked(uid) as db:
            rows=list(reversed(self.history(db,uid)))
            if before is not None:rows=[r for r in rows if r['id']<int(before)]
            return dict(transactions=rows[:50],next_before=rows[49]['id'] if len(rows)>50 else None)

    def portfolio(self, uid):
        with self.locked(uid) as db:
            cash=money(dec(db.execute('SELECT cash FROM portfolios WHERE user_id=?',(uid,)).fetchone()['cash']))
            rows=db.execute('SELECT * FROM positions WHERE user_id=? ORDER BY symbol',(uid,)).fetchall()
            history=self.history(db,uid)
            legacy = db.execute('''SELECT COUNT(*) AS n FROM trades t LEFT JOIN paper_trade_details d
                ON d.trade_id=t.id WHERE t.user_id=? AND d.id IS NULL''',(uid,)).fetchone()['n']
        holdings=[]; basis=Decimal(0); invested=Decimal(0); complete=True; quotes={}
        for r in rows:
            shares=dec(r['shares']).quantize(SHARE); average=dec(r['average_price']); cost=money(shares*average);basis+=cost
            item=dict(symbol=r['symbol'],company=r['symbol'],shares=text(shares),average_price=text(average),cost_basis=text(cost),
                      price=None,value=None,gain=None,gain_percent=None,quote_at=None,quote_status='unavailable')
            try:
                q,price,at=self.quote_data(r['symbol'])
                quotes[r['symbol']] = (q,price,at)
                value=money(shares*price);invested+=value
                item.update(company=str(q.get('name') or r['symbol']),price=text(price),value=text(value),gain=text(value-cost),
                            gain_percent=text(money((value-cost)/cost*100)) if cost else None,quote_at=at,quote_status='current')
            except PaperError:complete=False
            holdings.append(item)
        total=cash+invested
        day_gain = None
        if not legacy:
            try:
                today = datetime.fromtimestamp(self.clock(), NY).date()
                fills = [r for r in history if datetime.fromisoformat(r['timestamp']).astimezone(NY).date() == today]
                current = {r['symbol']: dec(r['shares']) for r in rows}
                daily = Decimal(0)
                for symbol in set(current) | {r['symbol'] for r in fills}:
                    q, price, at = quotes.get(symbol) or self.quote_data(symbol)
                    if datetime.fromisoformat(at).astimezone(NY).date() != today:
                        raise ValueError()
                    previous = dec(q['previous_close'])
                    if previous <= 0: raise ValueError()
                    opening = current.get(symbol, Decimal(0))
                    for fill in (r for r in fills if r['symbol'] == symbol):
                        quantity = dec(fill['shares']) * (1 if fill['side']=='BUY' else -1)
                        opening -= quantity
                        # Includes actual rounded fill cash flows.
                        daily += quantity*price - dec(fill['total'])*(1 if fill['side']=='BUY' else -1)
                    daily += opening*(price-previous)
                day_gain = text(money(daily))
            except (PaperError, ValueError, KeyError):
                pass
        return dict(simulation=True,currency='USD',cash=text(cash),starting_cash='10000',cost_basis=text(basis),
                    invested=text(invested) if complete else None,total_value=text(total) if complete else None,
                    unrealized=text(invested-basis) if complete else None,realized=text(money(cash+basis-10000)),
                    total_gain=text(total-10000) if complete else None,gain_percent=text(money((total-10000)/100)) if complete else None,
                    day_gain=day_gain,holdings=holdings,recent=list(reversed(history))[:10],supported_symbols=list(SYMBOLS),
                    valuation_status='current' if complete else 'unavailable')

    def reset(self, uid):
        with self.locked(uid) as db:
            db.execute('DELETE FROM paper_trade_details WHERE user_id=?',(uid,))
            db.execute('DELETE FROM trades WHERE user_id=?',(uid,))
            db.execute('DELETE FROM positions WHERE user_id=?',(uid,))
            db.execute('UPDATE portfolios SET cash=10000 WHERE user_id=?',(uid,))
            # Keep completed results for retry safety; invalidate all unfilled previews.
            db.execute('UPDATE paper_previews SET invalidated=1 WHERE user_id=? AND result IS NULL',(uid,))
        return dict(simulation=True,cash='10000')
