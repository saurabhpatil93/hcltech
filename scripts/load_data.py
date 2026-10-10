import csv,argparse
from pathlib import Path
from app.db import init_db,connect
TABLES={'customers':['customer_id','full_name','tier','city','joined_year'],'products':['sku','name','category','price','warranty_months'],'orders':['order_id','customer_id','order_date','status','payment_method','delivery_note'],'order_items':['order_id','sku','qty','net_unit_price','delivered_on'],'returns':['return_id','order_id','sku','requested_on','reason','status','refund_amount']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--dir',default='data/csv');root=Path(p.parse_args().dir);init_db()
 with connect() as c:
  for table,cols in TABLES.items():
   f=root/(table+'.csv')
   if not f.exists():print('SKIP',f);continue
   rows=list(csv.DictReader(f.open(newline='',encoding='utf-8-sig')))
   for r in rows:
    if any(k not in r for k in cols):raise ValueError(f'{f}: schema mismatch')
    vals=[r.get(k,'') or None if k=='delivered_on' else r.get(k,'') for k in cols]
    c.execute(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",vals)
   print(f'Loaded {len(rows)} into {table}')
if __name__=='__main__':main()
