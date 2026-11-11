from itertools import product, combinations
from pathlib import Path
from time import perf_counter
import logging
import pulp
from ..models import CFLPSolution

def lp_gap(milp,lp):
    if milp==0: return 0.0 if lp==0 else None
    return abs(milp-lp)/abs(milp)*100

class CFLPCalculator:
    def __init__(self,log_dir=None):
        self.log_dir=Path(log_dir) if log_dir else None
        self.counter=0

    def solve(self,data,*,single=False,big_m=False,relax=False):
        if single and big_m: raise ValueError('Эксперимент Big-M определён для Multi-Sourcing')
        cs=data.customers; fs=data.facilities; t=data.tariffs.values
        model=pulp.LpProblem('Logistics_CFLP',pulp.LpMinimize)
        y={f.facility_id:pulp.LpVariable('y_'+f.facility_id,0,1,cat='Continuous' if relax else 'Binary') for f in fs}
        z={}; x={}
        for c in cs:
            for f in fs:
                k=(f.facility_id,c.customer_id)
                if single:
                    z[k]=pulp.LpVariable('z_'+k[0]+'_'+k[1],0,1,cat='Continuous' if relax else 'Binary')
                    x[k]=c.demand_tons_year*z[k]
                    model+=z[k]<=y[f.facility_id]
                else:
                    x[k]=pulp.LpVariable('x_'+k[0]+'_'+k[1],lowBound=0)
        # Рубли сохраняются в целевой функции; CBC допускается только с нулевым относительным gap.
        model+=pulp.lpSum(f.fixed_cost_rub_year*y[f.facility_id] for f in fs)+pulp.lpSum(t[k]*v for k,v in x.items())
        for c in cs: model+=pulp.lpSum(x[(f.facility_id,c.customer_id)] for f in fs)==c.demand_tons_year
        for f in fs: model+=pulp.lpSum(x[(f.facility_id,c.customer_id)] for c in cs)<=(1e9 if big_m else f.capacity_tons_year)*y[f.facility_id]
        label=('single' if single else 'multi')+('_M' if big_m else '_K')+('_LP' if relax else '_MILP')
        kwargs={}
        self.counter+=1
        if self.log_dir:
            self.log_dir.mkdir(parents=True,exist_ok=True)
            kwargs['logPath']=str(self.log_dir/f'cbc_{self.counter:03d}_{label}.log')
        solver=pulp.PULP_CBC_CMD(msg=False,threads=0,gapRel=0,timeLimit=60,
                options=['randomSeed 1','integerTolerance 1e-9','primalTolerance 1e-9'],**kwargs)
        start=perf_counter(); model.solve(solver); elapsed=perf_counter()-start
        status=pulp.LpStatus[model.status]
        logging.getLogger('pipeline').info('CBC %s status=%s wall_seconds=%.6f',label,status,elapsed)
        if status!='Optimal' or model.sol_status!=pulp.LpSolutionOptimal:
            if status=='Optimal': status='Feasible_Not_Proven_Optimal'
            return CFLPSolution(label,status,None,None,None,{},{},{},{},{},{},{},{},{},elapsed)
        opens={k:float(v.value()) for k,v in y.items()}
        flows={f.facility_id:{c.customer_id:float(pulp.value(x[(f.facility_id,c.customer_id)])) for c in cs} for f in fs}
        assignments={f.facility_id:{c.customer_id:float(z[(f.facility_id,c.customer_id)].value()) for c in cs} for f in fs} if single else {}
        loads={j:sum(v.values()) for j,v in flows.items()}
        demand={c.customer_id:sum(flows[f.facility_id][c.customer_id] for f in fs)-c.demand_tons_year for c in cs}
        slacks={f.facility_id:(1e9 if big_m else f.capacity_tons_year)*opens[f.facility_id]-loads[f.facility_id] for f in fs}
        overloads={f.facility_id:max(0,loads[f.facility_id]-f.capacity_tons_year*opens[f.facility_id]) for f in fs}
        binary={k:min(abs(v),abs(1-v)) for k,v in opens.items()} if not relax else {}
        if single and not relax: binary.update({j+'_'+i:min(abs(v),abs(1-v)) for j,row in assignments.items() for i,v in row.items()})
        links={j+'_'+i:opens[j]-v for j,row in assignments.items() for i,v in row.items()}
        fixed=sum(f.fixed_cost_rub_year*opens[f.facility_id] for f in fs)
        transport=sum(t[(j,i)]*v for j,row in flows.items() for i,v in row.items())
        if max(map(abs,demand.values()))>1e-5 or min(slacks.values())<-.001 or (binary and max(binary.values())>1e-6):
            raise ArithmeticError(f'CBC {label}: недопустимый результат {demand}, {slacks}, {binary}')
        return CFLPSolution(label,status,float(pulp.value(model.objective)),fixed,transport,opens,flows,assignments,loads,demand,slacks,overloads,binary,links,elapsed)

def enumerate_single(data):
    """Независимый полный перебор всех 4^5 назначений без использования PuLP."""
    best=float('inf'); chosen=None
    for ids in product(range(len(data.facilities)),repeat=len(data.customers)):
        load=[0.0]*len(data.facilities)
        for c,j in zip(data.customers,ids): load[j]+=c.demand_tons_year
        if any(v>f.capacity_tons_year for v,f in zip(load,data.facilities)): continue
        cost=sum(f.fixed_cost_rub_year for f,v in zip(data.facilities,load) if v>0)
        cost+=sum(c.demand_tons_year*data.tariffs.values[(data.facilities[j].facility_id,c.customer_id)] for c,j in zip(data.customers,ids))
        if cost<best: best=cost; chosen=ids
    return dict(status='Optimal' if chosen is not None else 'Infeasible',objective_rub_year=best if chosen is not None else None,assignments=chosen)

def enumerate_multi(data,big_m=False):
    """16 наборов открытий; независимая транспортная LP через HiGHS/SciPy."""
    import numpy as np
    from scipy.optimize import linprog
    customers=data.customers; facilities=data.facilities; n=len(customers); m=len(facilities)
    c=np.array([data.tariffs.values[(f.facility_id,x.customer_id)] for f in facilities for x in customers])
    ae=np.zeros((n,n*m)); au=np.zeros((m,n*m))
    for j in range(m):
        for i in range(n): ae[i,j*n+i]=1; au[j,j*n+i]=1
    best=float('inf')
    for mask in product([0,1],repeat=m):
        cap=[(1e9 if big_m else f.capacity_tons_year)*v for f,v in zip(facilities,mask)]
        if sum(cap)<sum(x.demand_tons_year for x in customers): continue
        res=linprog(c,A_ub=au,b_ub=cap,A_eq=ae,b_eq=[x.demand_tons_year for x in customers],bounds=(0,None),method='highs')
        if res.success:
            cost=res.fun+sum(f.fixed_cost_rub_year*v for f,v in zip(facilities,mask))
            best=min(best,float(cost))
    return best if best<float('inf') else None
