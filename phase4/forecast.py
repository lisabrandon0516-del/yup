"""Explainable pre-action estimates. These are ranges, never promises."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Forecast:
    headline:str
    expected:str
    downside:str
    confidence:str
    affected:tuple[str,...]

def price_forecast(state,product_id:str,new_price:int)->Forecast:
    product=(getattr(state,'products',{}) or {}).get(product_id)
    old=int(getattr(product,'price',0) or 0); cost=int(getattr(product,'cost',0) or 0)
    if not old:return Forecast('Price change','Demand impact unknown','No historical price is available','Low',('Merchandising','Customers'))
    change=(new_price-old)/old
    margin=((new_price-cost)/new_price*100) if new_price else -100
    direction='Traffic may improve' if change<0 else 'Unit demand may soften'
    return Forecast('Price decision',f'{direction}; item margin would be about {margin:.1f}%.','Competitors or customers may respond differently than expected.','Moderate',('Merchandising','Inventory','Customers','Rivals'))

def order_forecast(state,items:dict[str,int])->Forecast:
    units=sum(max(0,int(v)) for v in items.values()); products=getattr(state,'products',{}) or {}
    cost=sum(max(0,int(q))*int(getattr(products.get(pid),'cost',0) or 0) for pid,q in items.items())
    return Forecast('Purchase order',f'{units:,} units would be ordered for an estimated {_money(cost)}.','Cash is committed before demand is known; excess stock may age.','High',('Ordering','Inventory','Accounting'))

def campaign_forecast(state,kind:str,category:str,budget:int)->Forecast:
    return Forecast('Campaign',f'{category} traffic and awareness may rise while the campaign runs.','Lift may be temporary, rivals may answer, and stockouts can erase gains.','Moderate',('Marketing','Customers','Inventory','Rivals'))

def _money(v):return f'${int(v or 0):,}'
