from __future__ import annotations
from .base import ModulePage

def _attr(obj,name,default=None): return getattr(obj,name,default) if obj is not None else default

def _list(obj,name):
    value=_attr(obj,name,[]) or []
    return list(value.values()) if isinstance(value,dict) else list(value)

class OrderingPage(ModulePage):
    title='Ordering'; deck='Purchase orders, deliveries, vendors, and receiving.'
    columns=('PO','Vendor','Placed','Arrival','Cost','Status'); kpis=('Open POs','Inbound Cost','Due Today','Late')
    def refresh(self):
        orders=_list(self._state,'orders'); rows=[]
        for o in orders: rows.append((_attr(o,'id','PO'),_attr(o,'supplier_id','—'),_attr(o,'placed_on','—'),_attr(o,'arrives_on','—'),f'${int(_attr(o,"cost",0) or 0)/100:,.2f}','Open'))
        self.table.set_rows(rows); self.set_kpi(0,str(len(rows))); self.set_kpi(1,f'${sum(int(_attr(o,"cost",0) or 0) for o in orders)/100:,.0f}')

class CustomersPage(ModulePage):
    title='Customers'; deck='ShopperLife households, loyalty, missions, and switching risk.'
    columns=('Segment','Households','Share of Trips','Avg Basket','At Risk','Primary Driver'); kpis=('Active Households','Loyal','At Risk','Avg Basket')
    def refresh(self):
        world=_attr(_attr(self._state,'rival_ai',None),'_live',{}) or {}; shoppers=(world.get('world',{}) if isinstance(world,dict) else {}).get('shoppers',{})
        rows=[]
        for city,book in shoppers.items():
            for cohort,shares in (book or {}).items(): rows.append((f'{city.title()} · {cohort.replace("_"," ").title()}','—',' / '.join(f'{k}:{v/10:.1f}%' for k,v in shares.items()),'—','—','Price, habit, availability'))
        self.table.set_rows(rows); self.set_kpi(0,str(len(rows)),'tracked cohorts')

class MarketingPage(ModulePage):
    title='Marketing'; deck='Campaign calendar, spend, targeting, and measured outcomes.'
    columns=('Campaign','Channel','Audience','Spend','Status','Measured Lift'); kpis=('Active Campaigns','Spend','Traffic Lift','Retention')
    def refresh(self):
        campaign=_attr(self._state,'campaign',None); rows=[]
        if campaign: rows.append((_attr(campaign,'kind','Campaign'),_attr(campaign,'kind','—'),_attr(campaign,'category','All'),f'${int(_attr(campaign,"cost",0) or 0)/100:,.2f}','Active','Pending'))
        self.table.set_rows(rows); self.set_kpi(0,str(len(rows)),'running now','good' if rows else 'neutral')

class RivalsPage(ModulePage):
    title='Rivals'; deck='Living Market intelligence and MarketMind strategic assessment.'
    columns=('Company','Doctrine','Stores','Price Index','Strategic Era','Last Move'); kpis=('Active Rivals','Competitive Pressure','Open Fights','Confidence')
    def refresh(self):
        rows=[]
        try:
            from open_late.rival_ai import rival_snapshot
            snap=rival_snapshot(self._state) if self._state is not None else {}
            for c in snap.get('chains') or []: rows.append((c.get('name'),c.get('doctrine','—'),c.get('open_stores',0),c.get('price_index','—'),c.get('strategic_era','—'),c.get('last_move','—')))
        except Exception: snap={}
        self.table.set_rows(rows); self.set_kpi(0,str(len(rows))); self.set_kpi(3,'Estimated','Public signals only','info')

class OperationsPage(ModulePage):
    title='Daily Operations'; deck='Hours, opening readiness, deliveries, staffing, and floor status.'
    columns=('Store','Open','Close','Staffing','Deliveries','Readiness'); kpis=('Open Stores','Ready','Exceptions','Next Event')
    def refresh(self): self.table.set_rows([])

PAGE_CLASSES={
 'orders':OrderingPage,'customers':CustomersPage,'marketing':MarketingPage,
 'market':RivalsPage,'settings':OperationsPage,
}
