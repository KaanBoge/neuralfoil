import numpy as np, neuralfoil as nf
def naca4(m,p,t,n=80):
    x=0.5*(1+np.cos(np.pi*np.arange(n+1)/n))
    yt=t/0.2*(0.2969*np.sqrt(x)-0.1260*x-0.3516*x**2+0.2843*x**3-0.1036*x**4)
    yc=np.where(x<p,m/p**2*(2*p*x-x**2),m/(1-p)**2*((1-2*p)+2*p*x-x**2)) if p>0 else np.zeros_like(x)
    dy=np.where(x<p,2*m/p**2*(p-x),2*m/(1-p)**2*(p-x)) if p>0 else np.zeros_like(x)
    th=np.arctan(dy)
    up=np.column_stack([x-yt*np.sin(th),yc+yt*np.cos(th)])
    lo=np.column_stack([x+yt*np.sin(th),yc-yt*np.cos(th)])[::-1]
    return np.vstack([up,lo[1:]])
c=naca4(0.02,0.3,0.09)
print("Ferri gate at TRUE Re (Guidonia band 0.34-0.42e6), alpha 0, exp cd 0.0116:")
for Re in [0.34e6,0.38e6,0.42e6]:
    for nc in [4,6,9]:
        r=nf.get_aero_from_coordinates(c,alpha=0,Re=Re,model_size="xlarge",n_crit=nc,xtr_upper=1,xtr_lower=1)
        print(f"  Re {Re/1e6:.2f}e6 ncrit {nc}: CL={np.asarray(r['CL']).item():.3f} CD={np.asarray(r['CD']).item():.5f} gap={(0.0116-np.asarray(r['CD']).item())*1e4:.1f} cts")
