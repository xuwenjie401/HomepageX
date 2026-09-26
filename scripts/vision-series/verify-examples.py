"""Numerical verification of worked examples; not a model/benchmark evaluation."""
import numpy as np
from math import log
# LK: independently assemble normal equations from gradient/residual samples.
J=np.array([[1.,0],[0,1],[1,1]]);r=np.array([-2.,-1,-3])
assert np.allclose(np.linalg.solve(J.T@J,-J.T@r),[2,1])
# Marginal mass constraints for SuperGlue and SALAD examples.
sg=np.array([[1,0,0],[0,1,0],[0,0,1],[0,0,2]])
assert np.allclose(sg.sum(1),[1,1,1,2]) and np.allclose(sg.sum(0),[1,1,3])
sa=np.array([[.8,.2,0],[.2,.7,.1],[0,.1,.9],[0,0,1]])
assert np.allclose(sa.sum(1),1) and np.allclose(sa.sum(0),[1,1,2])
assert np.isclose(-np.array([.8,.1,.1])@np.log([.6,.2,.2]),.730548,atol=1e-6)
# Sparse NRE probabilities and softargmax gradient.
z=np.array([.9,.7,.2])/.1;prob=np.exp(z-z.max());prob/=prob.sum()
assert np.allclose(prob,[.880090,.119107,.000803],atol=1e-6)
c=np.array([-1.,0,1]);mass=np.array([.1,.3,.6]);assert np.isclose(mass@c,.5)
# Gram's invariance to orthogonal feature-coordinate change.
X=np.array([[1.,0],[0,1],[2**-.5,2**-.5]]);Q=np.array([[0.,-1],[1,0]])
assert np.allclose(X@X.T,(X@Q)@(X@Q).T)
assert np.linalg.eigvalsh([[1,.9,.1],[.9,1,.2],[.1,.2,1]]).min()>0
# Schur complement vs full solve.
Hcc=np.array([[4.,1],[1,3]]);Hcp=np.array([[1.],[2.]])
H=np.block([[Hcc,Hcp],[Hcp.T,np.array([[2.]])]])
g=np.array([1.,-1,2]);S=Hcc-Hcp@Hcp.T/2
assert np.allclose(S,[[3.5,0],[0,1]])
assert np.allclose(np.linalg.solve(H,-g),[0,3,-4])
# Finite differences verify the projection Jacobian for a left pose perturbation.
P=np.array([.4,-.2,4.]);fx,fy=320.,300.
def skew(v):x,y,z=v;return np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
def expR(w):
 a=np.linalg.norm(w)
 if a==0:return np.eye(3)
 K=skew(w/a);return np.eye(3)+np.sin(a)*K+(1-np.cos(a))*(K@K)
def residual(delta):
 p=expR(delta[3:])@P+delta[:3];return -np.array([fx*p[0]/p[2],fy*p[1]/p[2]])
Jpi=np.array([[fx/P[2],0,-fx*P[0]/P[2]**2],[0,fy/P[2],-fy*P[1]/P[2]**2]])
Ja=-Jpi@np.column_stack([np.eye(3),-skew(P)])
eps=1e-7;Jn=np.column_stack([(residual(np.eye(6)[i]*eps)-residual(-np.eye(6)[i]*eps))/(2*eps) for i in range(6)])
assert np.allclose(Ja,Jn,atol=1e-6)
# Sim(3) storage's projective equivalence, and constrained loop-error distribution.
s=1.7;t=np.array([.2,-.1,.3]);a=s*P+t;b=P+t/s
assert np.allclose(a[:2]/a[2],b[:2]/b[2])
variance=np.array([1.,1,4]);correction=-6*variance/variance.sum()
assert np.allclose(correction,[-1,-1,-4]) and np.isclose(correction.sum(),-6)
print('PASS: LK, transport marginals, cross-entropy, sparse NRE, subpixel position, Gram, Schur, pose Jacobian, Sim(3), loop-error allocation.')
