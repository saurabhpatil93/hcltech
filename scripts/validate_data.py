import csv,argparse
from pathlib import Path
from datetime import date
def read(p):
 p=Path(p)
 return list(csv.DictReader(p.open(newline='',encoding='utf-8-sig'))) if p.exists() else []
def validate(directory='data/csv'):
 d=Path(directory);cs=read(d/'customers.csv');ps=read(d/'products.csv');os_=read(d/'orders.csv');its=read(d/'order_items.csv');rs=read(d/'returns.csv');errors=[]
 cust={x['customer_id']:x for x in cs};prod={x['sku']:x for x in ps};orders={x['order_id']:x for x in os_}
 for rows,key,label in [(cs,'customer_id','customers'),(ps,'sku','products'),(os_,'order_id','orders'),(rs,'return_id','returns')]:
  if len({r[key] for r in rows})!=len(rows):errors.append(f'{label}: duplicate {key}')
 if len(cs)<30:errors.append('Need at least 30 customers')
 if len(ps)<20:errors.append('Need at least 20 products')
 if len(os_)<60:errors.append('Need at least 60 orders')
 if len({r['tier'] for r in cs})<2:errors.append('Need at least 2 tiers')
 if len({r['category'] for r in ps})<5:errors.append('Need at least 5 categories')
 for r in cs:
  if not (len(r['customer_id'])==5 and r['customer_id'][0]=='C' and r['customer_id'][1:].isdigit()):errors.append('Bad customer ID '+r['customer_id'])
  if r['tier'] not in {'STANDARD','GOLD','PLATINUM'}:errors.append('Bad tier '+r['customer_id'])
  if r['customer_id'][1:].isdigit() and 9000<=int(r['customer_id'][1:])<=9999:errors.append('Reserved customer ID '+r['customer_id'])
 for r in ps:
  if float(r['price'])<=0 or int(r['warranty_months'])<0:errors.append('Invalid product '+r['sku'])
  if r['sku'].startswith('SKU-JDG'):errors.append('Reserved SKU '+r['sku'])
 for r in os_:
  if r['customer_id'] not in cust:errors.append('Unknown customer for '+r['order_id'])
  if r['order_id'].startswith('O-9'):errors.append('Reserved order '+r['order_id'])
  try:date.fromisoformat(r['order_date'])
  except Exception:errors.append('Bad order date '+r['order_id'])
 itemkeys=set()
 for r in its:
  k=(r['order_id'],r['sku']);itemkeys.add(k)
  if r['order_id'] not in orders:errors.append('Unknown order '+str(k));continue
  if r['sku'] not in prod:errors.append('Unknown SKU '+str(k));continue
  if int(r['qty'])<1:errors.append('Quantity below 1 '+str(k))
  if not 0<float(r['net_unit_price'])<=float(prod[r['sku']]['price']):errors.append('Net price invalid '+str(k))
  if r['delivered_on']:
   if orders[r['order_id']]['status']!='DELIVERED':errors.append('Delivery date on non-delivered order '+str(k))
   try:
    if date.fromisoformat(r['delivered_on'])<date.fromisoformat(orders[r['order_id']]['order_date']):errors.append('Delivery before order '+str(k))
   except Exception:errors.append('Bad delivery date '+str(k))
  elif orders[r['order_id']]['status']=='DELIVERED':errors.append('Delivered order missing delivery date '+str(k))
 for r in rs:
  if (r['order_id'],r['sku']) not in itemkeys:errors.append('Return refers to missing item '+r['order_id']+'/'+r['sku'])
 return errors,{'customers':len(cs),'products':len(ps),'orders':len(os_),'order_items':len(its),'returns':len(rs)}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dir',default='data/csv');a=p.parse_args();e,c=validate(a.dir);print('Counts:',c)
 if e:print('VALIDATION FAILED');[print('-',x) for x in e];raise SystemExit(1)
 print('VALIDATION PASSED')
