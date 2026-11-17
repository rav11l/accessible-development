"""Reproduce illustrative models in WP-2026-10 version 2.0."""
from pathlib import Path
import json,csv,math,argparse
def write_csv(path,headers,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(headers);w.writerows(rows)
def run(base):
    base=Path(base);p=json.loads((base/'parameters.json').read_text(encoding='utf8'));b=p['baseline']
    T=b['years'];r=b['real_discount_rate'];Q=b['eligible_operations_per_year']
    out=base/'calculated';out.mkdir(exist_ok=True)
    def calc(adoption,s=None,loss=0,replace=0):
        s=b['resource_saving_per_operation'] if s is None else s
        flows=[Q*a*s-b['operating_cost_per_year']-loss-(replace if t==p['replacement_year'] else 0) for t,a in enumerate(adoption,1)]
        return -b['initial_investment']+sum(x/(1+r)**t for t,x in enumerate(flows,1))+b['residual_value']/(1+r)**T,flows
    steady=[b['adoption']]*T;A=sum((1+r)**(-t) for t in range(1,T+1));base_npv,_=calc(steady)
    entry=[(f,f/p['private_entry']['saving_per_operation']) for f in p['private_entry']['fixed_costs']]
    savings=[(s,calc(steady,s=s)[0]) for s in p['saving_sensitivity']]
    threshold=(b['initial_investment']/A+b['operating_cost_per_year'])/(Q*b['resource_saving_per_operation'])
    s_base=b['resource_saving_per_operation'];s_low=min(p['saving_sensitivity'])
    assert len(p['ramp_adoption'])==T, 'Ramp length must equal the evaluation horizon'
    cases=[
      ('Базовый постоянный охват',steady,s_base,0,0),
      (f'Экономия {s_low:g} единиц',steady,s_low,0,0),
      ('Поэтапное подключение',p['ramp_adoption'],s_base,0,0),
      ('Подключение и ежегодные потери',p['ramp_adoption'],s_base,p['annual_loss_stress'],0),
      ('Подключение потери и замена',p['ramp_adoption'],s_base,p['annual_loss_stress'],p['replacement_cost'])
    ]
    lifecycle=[];yearly=[]
    for name,a,s,loss,replace in cases:
        v,flows=calc(a,s,loss,replace);lifecycle.append({'name':name,'npv':v})
        yearly.append([name,0,0,-b['initial_investment'],-b['initial_investment']])
        yearly.extend([name,t,a[t-1],flow,flow/(1+r)**t] for t,flow in enumerate(flows,1))
    low=calc(p['ramp_adoption'],s_low,p['annual_loss_stress'],p['replacement_cost'])[0]
    sc=p['scenarios'];paths=[]
    for year in range(sc['start_year'],sc['end_year']+1):
        t=year-sc['start_year']
        paths.append([year]+[sc['initial_adoption']+(x['maximum']-sc['initial_adoption'])*(1-math.exp(-x['speed']*t)) for x in sc['paths']])
    assert abs(calc([threshold]*T)[0])<1e-6
    assert all(0<=v<=1 for row in paths for v in row[1:])
    assert all(paths[0][i+1]==sc['initial_adoption'] for i in range(len(sc['paths'])))
    default_b={'years':10,'initial_investment':10000000,'eligible_operations_per_year':200000,'adoption':0.5,'resource_saving_per_operation':50,'operating_cost_per_year':1000000,'real_discount_rate':0.08,'residual_value':0}
    if b==default_b and p['ramp_adoption']==[.1,.2,.3,.4,.5,.5,.5,.5,.5,.5] and p['annual_loss_stress']==500000 and p['replacement_year']==5 and p['replacement_cost']==4000000:
        assert abs(base_npv-16840325.59576577)<1e-6
        assert calc(steady,20)[0]<0
        assert abs(lifecycle[-1]['npv']-2164537.6087141894)<1e-6
    write_csv(out/'entry_thresholds.csv',['fixed_cost','operations_break_even'],entry)
    write_csv(out/'saving_sensitivity.csv',['resource_saving','npv'],savings)
    write_csv(out/'lifecycle_npv.csv',['case','npv','change_from_base'],[(x['name'],x['npv'],x['npv']-base_npv) for x in lifecycle])
    write_csv(out/'annual_cashflows.csv',['case','year','adoption','net_resource_flow','present_value'],yearly)
    write_csv(out/'scenarios_2050.csv',['year']+[x['name'] for x in sc['paths']],paths)
    result={'annuity_factor':A,'base_npv':base_npv,'adoption_break_even':threshold,'lifecycle':lifecycle,'combined_low_saving':low}
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    egdi=[('Эстония',.9727),('Литва',.9110),('Казахстан',.9009),('Латвия',.8852),('Украина',.8841),('Россия',.8532),('Армения',.8422),('Узбекистан',.7999),('Грузия',.7792),('Молдова',.7719),('Азербайджан',.7607),('Беларусь',.7445),('Кыргызстан',.7316),('Таджикистан',.5606),('Туркменистан',.4751)]
    write_csv(base/'data_egdi_2024.csv',['country','egdi','year','source'],[(n,v,2024,'UN DESA E-Government Survey 2024 Appendix pp 172-179; WP reference 11') for n,v in egdi])
    return result
def plots(base):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    base=Path(base);p=json.loads((base/'parameters.json').read_text(encoding='utf8'));out=base/'calculated'
    def read(name):
        with (out/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    with (base/'data_egdi_2024.csv').open(encoding='utf-8-sig') as f:egdi=list(csv.DictReader(f))
    fig,ax=plt.subplots(figsize=(8,6));ax.barh([x['country'] for x in egdi][::-1],[float(x['egdi']) for x in egdi][::-1])
    ax.set(xlim=(0,1),xlabel='EGDI',title='Электронное правительство 2024');fig.tight_layout();fig.savefig(out/'01_egdi.png',dpi=180);plt.close(fig)
    rows=read('entry_thresholds.csv');fig,ax=plt.subplots()
    ax.bar([x['fixed_cost'] for x in rows],[float(x['operations_break_even']) for x in rows])
    ax.set(xlabel='Фиксированные расходы',ylabel='Число операций',title='Иллюстративный порог участия')
    fig.tight_layout();fig.savefig(out/'02_entry.png',dpi=180);plt.close(fig)
    rows=read('saving_sensitivity.csv');fig,ax=plt.subplots()
    ax.plot([float(x['resource_saving']) for x in rows],[float(x['npv'])/1e6 for x in rows],marker='o');ax.axhline(0,color='gray')
    ax.set(xlabel='Экономия на операцию',ylabel='NPV млн условных единиц',title='Иллюстративная чувствительность')
    fig.tight_layout();fig.savefig(out/'03_npv.png',dpi=180);plt.close(fig)
    rows=read('scenarios_2050.csv');fig,ax=plt.subplots()
    for x in p['scenarios']['paths']:ax.plot([int(z['year']) for z in rows],[float(z[x['name']])*100 for z in rows],label=x['name'])
    ax.legend();ax.set(xlabel='Год',ylabel='Доля подходящих операций %',title='Условные траектории без калибровки')
    fig.tight_layout();fig.savefig(out/'04_scenarios.png',dpi=180);plt.close(fig)
if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--plots',action='store_true');args=cli.parse_args()
    here=Path(__file__).resolve().parent
    print(json.dumps(run(here),ensure_ascii=False,indent=2))
    if args.plots:plots(here)

