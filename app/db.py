import sqlite3
from contextlib import contextmanager
from app.config import SQLITE_PATH
SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS customers(customer_id TEXT PRIMARY KEY,full_name TEXT NOT NULL,tier TEXT NOT NULL CHECK(tier IN ('STANDARD','GOLD','PLATINUM')),city TEXT NOT NULL,joined_year INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS products(sku TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,price REAL NOT NULL CHECK(price>0),warranty_months INTEGER NOT NULL CHECK(warranty_months>=0));
CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(customer_id),order_date TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('PLACED','SHIPPED','DELIVERED','CANCELLED')),payment_method TEXT NOT NULL CHECK(payment_method IN ('UPI','CARD','COD')),delivery_note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS order_items(order_id TEXT NOT NULL REFERENCES orders(order_id),sku TEXT NOT NULL REFERENCES products(sku),qty INTEGER NOT NULL CHECK(qty>=1),net_unit_price REAL NOT NULL CHECK(net_unit_price>0),delivered_on TEXT,PRIMARY KEY(order_id,sku));
CREATE TABLE IF NOT EXISTS returns(return_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,sku TEXT NOT NULL,requested_on TEXT NOT NULL,reason TEXT NOT NULL CHECK(reason IN ('DEFECTIVE','DAMAGED','WRONG_ITEM','CHANGED_MIND')),status TEXT NOT NULL CHECK(status IN ('REQUESTED','PICKED_UP','REFUNDED','REJECTED')),refund_amount REAL NOT NULL DEFAULT 0,FOREIGN KEY(order_id,sku) REFERENCES order_items(order_id,sku));
CREATE TABLE IF NOT EXISTS rule_registry(rule_id TEXT PRIMARY KEY,description TEXT NOT NULL,parameter TEXT NOT NULL,operator TEXT NOT NULL,value TEXT NOT NULL,scope_categories TEXT NOT NULL DEFAULT 'ALL',scope_tiers TEXT NOT NULL DEFAULT 'ALL',effective_from TEXT NOT NULL,effective_to TEXT NOT NULL DEFAULT '',source_doc_id TEXT NOT NULL,source_section TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_register(doc_id TEXT PRIMARY KEY,filename TEXT NOT NULL,authority_level INTEGER NOT NULL,category TEXT NOT NULL DEFAULT 'GENERAL',scope_tiers TEXT NOT NULL DEFAULT 'ALL',effective_from TEXT NOT NULL,effective_to TEXT NOT NULL DEFAULT '',version TEXT NOT NULL DEFAULT '1.0',source_url TEXT NOT NULL DEFAULT '',synthetic TEXT NOT NULL DEFAULT 'N',supersedes TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS audit_records(trace_id TEXT PRIMARY KEY,timestamp TEXT NOT NULL,customer_id TEXT,question_category TEXT,question_redacted TEXT,sources_retrieved TEXT,precedence_decisions TEXT,tools_invoked TEXT,answer_type TEXT,model TEXT,latency_ms INTEGER,response_json TEXT);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
"""
@contextmanager
def connect():
 SQLITE_PATH.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(SQLITE_PATH,timeout=20); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON')
 try: yield c; c.commit()
 finally: c.close()
def init_db():
 with connect() as c: c.executescript(SCHEMA)
