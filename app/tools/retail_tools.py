from datetime import date
import calendar
from app.db import connect
def _rule(param,asof,category,tier,default=None):
 with connect() as c: rows=c.execute("SELECT r.*,s.authority_level FROM rule_registry r LEFT JOIN source_register s ON s.doc_id=r.source_doc_id WHERE r.parameter=? AND r.effective_from<=? AND (r.effective_to='' OR r.effective_to>=?) AND (r.scope_categories='ALL' OR r.scope_categories=? OR r.scope_categories LIKE ?) AND (r.scope_tiers='ALL' OR r.scope_tiers=?)",(param,asof,asof,category,'%'+category+'%',tier)).fetchall()
 if not rows: return default,None
 rows=sorted(rows,key=lambda r:(int(r['authority_level'] or 5),r['effective_from']),reverse=False); topauth=min(int(r['authority_level'] or 5) for r in rows); top=[r for r in rows if int(r['authority_level'] or 5)==topauth]
 if len({r['value'] for r in top})>1: return None,{'conflict':True}
 r=max(top,key=lambda x:x['effective_from']); v=r['value']
 try:v=float(v)
 except ValueError:pass
 return v,dict(r)
def order_lookup(cid,oid):
 with connect() as c: rows=c.execute('SELECT o.order_id,o.status,o.order_date,oi.sku,oi.qty,oi.net_unit_price,oi.delivered_on,p.name,p.category FROM orders o JOIN order_items oi USING(order_id) JOIN products p USING(sku) WHERE o.order_id=? AND o.customer_id=?',(oid,cid)).fetchall()
 if not rows:return {'status':'not_found','message':'I could not find an order for this signed-in customer.'}
 return {'status':'ok','order_id':oid,'items':[dict(r) for r in rows]}
def check_return_eligibility(cid,oid,sku,asof):
 with connect() as c:
  r=c.execute('SELECT o.customer_id,o.status,oi.delivered_on,oi.qty,oi.net_unit_price,p.category FROM orders o JOIN order_items oi USING(order_id) JOIN products p USING(sku) WHERE o.order_id=? AND oi.sku=?',(oid,sku)).fetchone(); ex=c.execute('SELECT status FROM returns WHERE order_id=? AND sku=?',(oid,sku)).fetchone(); cust=c.execute('SELECT tier FROM customers WHERE customer_id=?',(cid,)).fetchone()
 if not r or r['customer_id']!=cid:return {'status':'not_found','message':'I could not find an order item for this signed-in customer.'}
 if r['status']!='DELIVERED':return {'status':'ineligible','reason':'Order has not been delivered.'}
 if ex:return {'status':'ineligible','reason':'A return already exists.'}
 if not r['delivered_on']:return {'status':'ineligible','reason':'Delivery date is missing.'}
 tier=cust['tier'] if cust else 'STANDARD'; days=(date.fromisoformat(asof)-date.fromisoformat(r['delivered_on'])).days
 if days<0:return {'status':'ineligible','reason':'As-of date is before delivery.'}
 window,rule=_rule('return_window_days',asof,r['category'],tier)
 if window is None:return {'status':'conflict' if rule else 'not_found','reason':'Return rule missing or conflicting.'}
 nr,_=_rule('non_returnable',asof,r['category'],tier,0)
 if nr:return {'status':'ineligible','reason':'Product category is non-returnable.','days_since_delivery':days}
 return {'status':'eligible' if days<=int(window) else 'ineligible','days_since_delivery':days,'return_window_days':int(window),'rule_source':rule.get('source_doc_id') if rule else None}
def calculate_refund(cid,oid,sku,asof):
 e=check_return_eligibility(cid,oid,sku,asof)
 if e['status']!='eligible':return {'status':'cannot_calculate','eligibility':e}
 with connect() as c:r=c.execute('SELECT oi.qty,oi.net_unit_price,p.category,cu.tier FROM orders o JOIN order_items oi USING(order_id) JOIN products p USING(sku) JOIN customers cu ON cu.customer_id=o.customer_id WHERE o.order_id=? AND oi.sku=? AND o.customer_id=?',(oid,sku,cid)).fetchone()
 subtotal=round(r['qty']*r['net_unit_price'],2); fee,fr=_rule('restocking_fee_pct',asof,r['category'],r['tier'],0); limit,lr=_rule('auto_refund_limit',asof,r['category'],r['tier'],10000)
 if fee is None or limit is None:return {'status':'conflict','message':'Conflicting refund rule; contact support.'}
 fee_amt=round(subtotal*float(fee)/100,2); refund=round(subtotal-fee_amt,2)
 return {'status':'calculated','currency':'INR','quantity':r['qty'],'net_unit_price':r['net_unit_price'],'net_subtotal':subtotal,'restocking_fee_pct':fee,'restocking_fee':fee_amt,'refund_amount':refund,'requires_human_approval':refund>float(limit),'rule_sources':[x.get('source_doc_id') for x in (fr,lr) if x]}
def check_warranty(cid,oid,sku,asof):
 with connect() as c:r=c.execute('SELECT o.customer_id,oi.delivered_on,p.warranty_months,p.name FROM orders o JOIN order_items oi USING(order_id) JOIN products p USING(sku) WHERE o.order_id=? AND oi.sku=?',(oid,sku)).fetchone()
 if not r or r['customer_id']!=cid:return {'status':'not_found','message':'I could not find an order item for this signed-in customer.'}
 if not r['delivered_on']:return {'status':'not_applicable','reason':'Delivery date unavailable.'}
 start=date.fromisoformat(r['delivered_on']); months=int(r['warranty_months']); y=start.year+(start.month-1+months)//12; m=(start.month-1+months)%12+1; end=date(y,m,min(start.day,calendar.monthrange(y,m)[1]))
 return {'status':'valid' if months>0 and date.fromisoformat(asof)<=end else 'expired_or_none','product':r['name'],'warranty_months':months,'warranty_end':end.isoformat(),'as_of_date':asof}
