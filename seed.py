import hashlib
from sqlalchemy import select
from models import Account, Company, CompanyUser, CompanyUserRole, Concept, Permission, Role, RolePermission, User

PERMISSIONS={"company.users.read":("Ver usuarios","Ver usuarios"),"company.users.write":("Administrar usuarios","Administrar usuarios"),"accounts.read":("Ver cuentas","Ver cuentas"),"accounts.write":("Crear cuentas","Crear cuentas"),"concepts.read":("Ver conceptos","Ver conceptos"),"concepts.write":("Crear conceptos","Crear conceptos"),"transactions.read":("Ver movimientos","Ver movimientos"),"transactions.write":("Registrar movimientos","Registrar movimientos"),"roles.read":("Ver roles","Ver roles"),"roles.write":("Configurar roles","Configurar roles")}
ROLE_PERMISSIONS={"ADMINISTRADOR":set(PERMISSIONS),"CONTADOR":{"company.users.read","accounts.read","accounts.write","concepts.read","concepts.write","transactions.read","transactions.write","roles.read"},"CAPTURISTA":{"accounts.read","concepts.read","transactions.read","transactions.write"},"CONSULTA":{"company.users.read","accounts.read","concepts.read","transactions.read"}}
def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()
def seed_database(db):
    roles={}
    for code in ROLE_PERMISSIONS:
        r=db.scalar(select(Role).where(Role.code==code))
        if not r: r=Role(code=code); db.add(r); db.flush()
        roles[code]=r
    perms={}
    for code,(name,desc) in PERMISSIONS.items():
        p=db.scalar(select(Permission).where(Permission.code==code))
        if not p: p=Permission(code=code,name=name,description=desc); db.add(p); db.flush()
        perms[code]=p
    for code,granted in ROLE_PERMISSIONS.items():
        if not db.scalar(select(RolePermission.id).where(RolePermission.role_id==roles[code].id)):
            for p in granted: db.add(RolePermission(role_id=roles[code].id,permission_id=perms[p].id))
    main=db.scalar(select(Company).where(Company.name=="Sistema General de Ingresos"))
    if not main: main=Company(name="Sistema General de Ingresos"); db.add(main); db.flush()
    for name,email,role,admin in [("Ana","ana@empresa.test","ADMINISTRADOR",True),("Luis","luis@empresa.test","CONTADOR",False),("María","maria@empresa.test","CAPTURISTA",False),("José","jose@empresa.test","CAPTURISTA",False),("Pedro","pedro@empresa.test","CONSULTA",False)]:
        u=db.scalar(select(User).where(User.email==email))
        if not u: u=User(name=name,email=email,password_hash=hash_password("secreto")); db.add(u); db.flush()
        m=db.scalar(select(CompanyUser).where(CompanyUser.company_id==main.id,CompanyUser.user_id==u.id))
        if not m: m=CompanyUser(company_id=main.id,user_id=u.id,is_admin=admin); db.add(m); db.flush(); db.add(CompanyUserRole(company_user_id=m.id,role_id=roles[role].id))
    if not db.scalar(select(Account).where(Account.company_id==main.id)): db.add(Account(company_id=main.id,name="Caja principal"))
    if not db.scalar(select(Concept).where(Concept.company_id==main.id)): db.add(Concept(company_id=main.id,name="Venta de servicios"))
    other=db.scalar(select(Company).where(Company.name=="Empresa Externa"))
    if not other: other=Company(name="Empresa Externa"); db.add(other); db.flush()
    u=db.scalar(select(User).where(User.email=="externo@otra.test"))
    if not u: u=User(name="Externo",email="externo@otra.test",password_hash=hash_password("secreto")); db.add(u); db.flush()
    if not db.scalar(select(CompanyUser).where(CompanyUser.company_id==other.id,CompanyUser.user_id==u.id)):
        m=CompanyUser(company_id=other.id,user_id=u.id); db.add(m); db.flush(); db.add(CompanyUserRole(company_user_id=m.id,role_id=roles["CONSULTA"].id))
    db.commit()
