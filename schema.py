import hmac, os
from datetime import datetime, timedelta, timezone
import jwt, strawberry
from sqlalchemy import select
from strawberry.fastapi import GraphQLRouter
from database import SessionLocal
from models import Account, CompanyUser, CompanyUserRole, Concept, Permission, Role, RolePermission, Transaction, User
from seed import hash_password

SECRET=os.getenv("JWT_SECRET")
if not SECRET: raise RuntimeError("JWT_SECRET es obligatorio; configúralo en .env")

@strawberry.type
class UserType: id:int; name:str; email:str
@strawberry.type
class AuthPayload: token:str|None; token_type:str|None; user:UserType|None
@strawberry.type
class AccountType: id:int; name:str
@strawberry.type
class ConceptType: id:int; name:str
@strawberry.type
class TransactionType: id:int; type:str; amount:float; description:str
@strawberry.type
class CompanyUserType: id:int; name:str
@strawberry.type
class RoleType: id:int; code:str
@strawberry.type
class PermissionType: id:int; code:str; name:str; description:str
@strawberry.input
class LoginInput: email:str; password:str
@strawberry.input
class AssignRoleInput: company_user_id:int; role_id:int
@strawberry.input
class SetRolePermissionsInput: role_id:int; permission_ids:list[int]

def actor(db,info):
    header=info.context["request"].headers.get("authorization","")
    if not header.startswith("Bearer "): raise ValueError("Acceso rechazado: falta Authorization: Bearer <token>")
    try: claims=jwt.decode(header[7:],SECRET,algorithms=["HS256"])
    except jwt.PyJWTError: raise ValueError("Acceso rechazado: token inválido o expirado")
    member=db.get(CompanyUser,claims.get("companyUserId"))
    if not member or not member.is_active or member.company_id!=claims.get("companyId"): raise ValueError("Acceso rechazado: membresía inválida")
    return member
def permit(db,member,code):
    ok=db.scalar(select(RolePermission.id).join(CompanyUserRole,CompanyUserRole.role_id==RolePermission.role_id).join(Permission,Permission.id==RolePermission.permission_id).where(CompanyUserRole.company_user_id==member.id,CompanyUserRole.is_active.is_(True),RolePermission.is_active.is_(True),Permission.is_active.is_(True),Permission.code==code))
    if not ok: raise ValueError(f"Acceso rechazado: falta el permiso {code}")
def usertype(u): return UserType(id=u.id,name=u.name,email=u.email)
def ptype(p): return PermissionType(id=p.id,code=p.code,name=p.name,description=p.description)

@strawberry.type
class Query:
 @strawberry.field
 def accounts(self,info:strawberry.Info)->list[AccountType]:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"accounts.read"); return [AccountType(id=x.id,name=x.name) for x in db.scalars(select(Account).where(Account.company_id==m.company_id)).all()]
 @strawberry.field
 def account(self,info:strawberry.Info,id:int)->AccountType:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"accounts.read"); x=db.get(Account,id)
   if not x or x.company_id!=m.company_id: raise ValueError("Acceso rechazado: cuenta de otra empresa")
   return AccountType(id=x.id,name=x.name)
 @strawberry.field
 def concepts(self,info:strawberry.Info)->list[ConceptType]:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"concepts.read"); return [ConceptType(id=x.id,name=x.name) for x in db.scalars(select(Concept).where(Concept.company_id==m.company_id)).all()]
 @strawberry.field
 def transactions(self,info:strawberry.Info)->list[TransactionType]:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"transactions.read"); return [TransactionType(id=x.id,type=x.type,amount=float(x.amount),description=x.description) for x in db.scalars(select(Transaction).where(Transaction.company_id==m.company_id)).all()]
 @strawberry.field
 def company_users(self,info:strawberry.Info)->list[CompanyUserType]:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"company.users.read"); return [CompanyUserType(id=x.id,name=x.user.name) for x in db.scalars(select(CompanyUser).where(CompanyUser.company_id==m.company_id)).all()]
 @strawberry.field
 def permission_catalog(self,info:strawberry.Info)->list[PermissionType]:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"roles.read"); return [ptype(x) for x in db.scalars(select(Permission).where(Permission.is_active.is_(True))).all()]

@strawberry.type
class Mutation:
 @strawberry.mutation
 def login(self,input:LoginInput)->AuthPayload:
  with SessionLocal() as db:
   u=db.scalar(select(User).where(User.email==input.email))
   if not u or not u.is_active or not hmac.compare_digest(u.password_hash,hash_password(input.password)): return AuthPayload(token=None,token_type=None,user=None)
   m=db.scalar(select(CompanyUser).where(CompanyUser.user_id==u.id,CompanyUser.is_active.is_(True)))
   if not m: return AuthPayload(token=None,token_type=None,user=None)
   token=jwt.encode({"companyUserId":m.id,"companyId":m.company_id,"exp":datetime.now(timezone.utc)+timedelta(minutes=30)},SECRET,algorithm="HS256")
   return AuthPayload(token=token,token_type="bearer",user=usertype(u))
 @strawberry.mutation
 def create_account(self,info:strawberry.Info,name:str)->AccountType:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"accounts.write"); x=Account(company_id=m.company_id,name=name); db.add(x); db.commit(); db.refresh(x); return AccountType(id=x.id,name=x.name)
 @strawberry.mutation
 def create_concept(self,info:strawberry.Info,name:str)->ConceptType:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"concepts.write"); x=Concept(company_id=m.company_id,name=name); db.add(x); db.commit(); db.refresh(x); return ConceptType(id=x.id,name=x.name)
 @strawberry.mutation
 def create_transaction(self,info:strawberry.Info,account_id:int,concept_id:int,type:str,amount:float,description:str)->TransactionType:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"transactions.write"); a=db.get(Account,account_id); c=db.get(Concept,concept_id)
   if not a or not c or a.company_id!=m.company_id or c.company_id!=m.company_id: raise ValueError("Cuenta o concepto inválido para la empresa")
   x=Transaction(company_id=m.company_id,account_id=account_id,concept_id=concept_id,type=type,amount=amount,description=description); db.add(x); db.commit(); db.refresh(x); return TransactionType(id=x.id,type=x.type,amount=float(x.amount),description=x.description)
 @strawberry.mutation
 def assign_role(self,info:strawberry.Info,input:AssignRoleInput)->CompanyUserType:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"roles.write"); target=db.get(CompanyUser,input.company_user_id); role=db.get(Role,input.role_id)
   if not target or not role or target.company_id!=m.company_id: raise ValueError("Usuario o rol inválido")
   for x in db.scalars(select(CompanyUserRole).where(CompanyUserRole.company_user_id==target.id)).all(): x.is_active=False
   x=db.scalar(select(CompanyUserRole).where(CompanyUserRole.company_user_id==target.id,CompanyUserRole.role_id==role.id))
   if x: x.is_active=True
   else: db.add(CompanyUserRole(company_user_id=target.id,role_id=role.id))
   db.commit(); return CompanyUserType(id=target.id,name=target.user.name)
 @strawberry.mutation
 def set_role_permissions(self,info:strawberry.Info,input:SetRolePermissionsInput)->RoleType:
  with SessionLocal() as db:
   m=actor(db,info); permit(db,m,"roles.write"); role=db.get(Role,input.role_id)
   if not role or role.code=="ADMINISTRADOR": raise ValueError("Rol inválido")
   for pair in db.scalars(select(RolePermission).where(RolePermission.role_id==role.id)).all(): pair.is_active=pair.permission_id in input.permission_ids
   db.commit(); return RoleType(id=role.id,code=role.code)

schema=strawberry.Schema(query=Query,mutation=Mutation)
graphql_app=GraphQLRouter(schema)
