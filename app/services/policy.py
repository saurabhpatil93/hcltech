def choose_precedence(hits,asof,category='GENERAL',tier='STANDARD'):
 usable=[]; decisions=[]
 for h in hits:
  m=h['metadata']
  if m.get('effective_from','0001-01-01')<=asof and (not m.get('effective_to') or m['effective_to']>=asof): usable.append(h)
 ids={h['metadata'].get('doc_id') for h in usable}; superseded=set()
 for h in usable:
  m=h['metadata']; sup=m.get('supersedes','')
  if sup in ids and sup and int(m.get('authority_level',5))<=2: superseded.add(sup); decisions.append(f"{m['doc_id']} supersedes {sup}")
 usable=[h for h in usable if h['metadata'].get('doc_id') not in superseded]
 if not usable: return [],decisions,False
 auth=min(int(h['metadata'].get('authority_level',5)) for h in usable); best=[h for h in usable if int(h['metadata'].get('authority_level',5))==auth]
 if len(best)<len(usable): decisions.append(f'Authority level {auth} overrides lower-authority source')
 latest=max(h['metadata'].get('effective_from','0001-01-01') for h in best); best=[h for h in best if h['metadata'].get('effective_from','0001-01-01')==latest]
 return best,decisions,False
