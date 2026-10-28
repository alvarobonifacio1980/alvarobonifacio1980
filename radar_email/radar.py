#!/usr/bin/env python3
"""Radar de vagas remotas: APIs públicas + busca indexada opcional, deduplicação, SMTP.

Nota: scores são estimativas conservadoras baseadas na descrição, NÃO equivalem
à verificação humana de todos os requisitos obrigatórios.
"""
import html
import json
import os
import re
import smtplib
import ssl
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "vistos.json"
TZ = ZoneInfo("America/Sao_Paulo")
TO = "alvarobonifacio1980@gmail.com"
SEARCHES = [
    '"professor" "TI" "remoto"', '"tutor" "EAD" "tecnologia"',
    '"instrutor" "Python" "remoto"', '"consultor" "TI" "remoto"',
    '"governança de TI" "remoto"', '"gerente de projetos" "remoto"',
    '"analista de negócios" "remoto"', '"analista de dados" "remoto"',
    '"Power BI" "remoto"', '"cientista de dados" "remoto"',
]
CATEGORIES = {
    "Docência e tutoria": ("professor", "docent", "tutor", "instrutor", "instructor", "trainer", "educator", "conteudista", "teaching", "teacher"),
    "Consultoria": ("consultor", "consultant", "implementation", "implantação", "implanta", "advisory"),
    "Gestão e governança TI": ("gerente", "coordenador", "gestor", "it manager", "service manager", "project manager", "delivery manager", "program manager", "governance", "governança", "pmo", "itil"),
    "Dados e negócios": ("data analyst", "analista de dados", "analista de negócios", "business analyst", "business intelligence", "analytics", "power bi", "bi analyst"),
    "IA e ciência de dados": ("data scientist", "cientista de dados", "machine learning", "ai engineer", "inteligência artificial", "ml engineer"),
    "Administração tecnológica": ("operations coordinator", "technical operations", "administrativo", "administrative", "support manager", "customer success"),
}
POSITIVE = {
    "Docência e tutoria": ("treinamento", "curso", "educa", "ensino", "training", "instructor", "tutor", "computing", "technology"),
    "Consultoria": ("implant", "process", "projeto", "project", "itil", "consult", "cliente", "client", "business", "sistema"),
    "Gestão e governança TI": ("itil", "sla", "service", "project", "governance", "governança", "observability", "gestão", "process", "kpi", "management"),
    "Dados e negócios": ("sql", "power bi", "python", "pandas", "etl", "dashboard", "analytics", "business"),
    "IA e ciência de dados": ("python", "machine learning", "deep learning", "data", "analytics", "scikit", "statistic", "time series"),
    "Administração tecnológica": ("process", "operations", "gestão", "itil", "sla", "service", "coordination"),
}
ENGLISH_STRONG = ("fluent english", "english fluency", "english c1", "english c2", "native english", "fluent in english", "advanced english required", "fluência em inglês")
ENGLISH_MID = ("advanced english", "english required", "english b2", "professional english", "inglês avançado", "inglês fluente")
HARD_BLOCK = ("100% presencial", "fully on-site", "on-site only", "on site only", "hybrid required", "híbrido obrigatório", "weekly office", "office 3 days", "presencial semanal", "phd required", "doctorate required", "doutorado obrigatório")
REMOTE_WORDS = ("remoto", "remote", "home office", "work from home", "anywhere", "teletrabalho")
INITIAL_SEEN = [
    "softexpert|consultor de implantação setor financeiro",
    "spread tecnologia|pmo pleno dados ia",
    "softexpert|consultor de implantação setor público",
    "semantix|analista sênior de governança de dados",
]
# Salário-base médio CLT Brasil - Portal Salário / Novo CAGED, atualizado em 08/10/2026.
# Referência de OCUPAÇÃO, não proposta salarial; nunca converter diretamente para PJ.
BENCHMARK = {
    "Docência e tutoria": (6364, "Professor de Informática no Ensino Superior, 26h/sem", "https://www.salario.com.br/profissao/professor-de-informatica-no-ensino-superior-cbo-234120/"),
    "Consultoria": (8458, "Consultor de TI, 42h/sem", "https://www.salario.com.br/profissao/consultor-de-tecnologia-da-informacao-cbo-212405/"),
    "Gestão e governança TI": (14040, "Gerente de Projetos de TI, 42h/sem", "https://www.salario.com.br/profissao/gerente-de-projetos-de-tecnologia-da-informacao-cbo-142520/"),
    "Dados e negócios": (5760, "Analista de BI, 42h/sem", "https://www.salario.com.br/profissao/analista-de-bi-business-intelligence/"),
    "IA e ciência de dados": (10356, "Cientista de Dados, 42h/sem", "https://www.salario.com.br/profissao/cientista-de-dados-data-scientist/"),
    "Administração tecnológica": (8458, "Analista de Sistemas (aproximação), 42h/sem", "https://www.salario.com.br/profissao/analista-de-sistemas-informatica-cbo-212405/"),
}

def now():
    return datetime.now(TZ)

def clean(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html.unescape(str(v or "")))).strip()

def norm(v):
    s = unicodedata.normalize("NFKD", clean(v).lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()

def fetch_json(url, *, method="GET", payload=None, headers=None):
    h = {"User-Agent": "RadarVagas/2.0 (portfolio academic)", "Accept": "application/json"}
    h.update(headers or {})
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def category(title):
    t = norm(title)
    for label, fragments in CATEGORIES.items():
        if any(norm(w) in t for w in fragments):
            return label
    return None

def job(title, company, desc, url, source, remote, regime="", date="", salary=""):
    title, company, desc = clean(title), clean(company), clean(desc)
    if not title or not company or not url.startswith("https://"):
        return None
    cat = category(title)
    if not cat:
        return None
    return dict(title=title, company=company, description=desc, url=url,
                source=source, remote=remote, regime=clean(regime) or "não informado",
                date=clean(date) or "não informada", salary=clean(salary),
                category=cat)

def remotive():
    data = fetch_json("https://remotive.com/api/remote-jobs")
    out = []
    for row in data.get("jobs", []):
        geo = norm(row.get("candidate_required_location"))
        if geo and not any(k in geo for k in ("worldwide", "anywhere", "global", "brazil", "brasil", "latam", "latin america", "south america")):
            continue
        j = job(row.get("title"), row.get("company_name"), row.get("description"), row.get("url",""),
                "Remotive", "compatível pela região declarada", row.get("job_type"),
                str(row.get("publication_date") or "")[:10], row.get("salary"))
        if j: out.append(j)
    return out

def himalayas():
    out = []
    for term in ("project manager", "data analyst", "consultant", "instructor", "data scientist", "business analyst"):
        data = fetch_json("https://himalayas.app/jobs/api/search?" + urllib.parse.urlencode({"q":term,"country":"BR","page":1}))
        for row in data.get("jobs",[]):
            regions = [norm(x.get("alpha2") or x.get("name")) if isinstance(x,dict) else norm(x) for x in row.get("locationRestrictions") or []]
            if regions and not any(x in ("br","brazil","brasil") for x in regions): continue
            desc = row.get("description") or row.get("excerpt")
            salary = ""
            if row.get("minSalary") is not None:
                salary = f"{row.get('currency') or ''} {row.get('minSalary')}–{row.get('maxSalary') or '?'} / {row.get('salaryPeriod') or 'período não informado'}"
            j = job(row.get("title"),row.get("companyName"),desc,row.get("applicationLink") or row.get("guid") or "",
                    "Himalayas", "restrição BR ou sem restrição declarada", row.get("employmentType"), str(row.get("pubDate") or ""), salary)
            if j: out.append(j)
    return out

def jobicy():
    data = fetch_json("https://jobicy.com/api/jobs?count=200")
    out = []
    for row in data.get("jobs", []):
        geo = norm(row.get("jobGeo"))
        if geo and not any(k in geo for k in ("anywhere","worldwide","brazil","brasil","latam","latin america","south america")): continue
        salary = ""
        if row.get("annualSalaryMin") and row.get("annualSalaryMax"):
            salary = f"{row.get('salaryCurrency') or 'moeda não informada'} {row['annualSalaryMin']}–{row['annualSalaryMax']} / ano"
        j = job(row.get("jobTitle"), row.get("companyName"), row.get("jobDescription"),
                row.get("url") or "", "Jobicy", "remoto: geografia BR/global declarada",
                row.get("jobType"), str(row.get("pubDate") or ""), salary)
        if j: out.append(j)
    return out

def serper_indexed():
    """Busca Google autorizada via Serper, em vez de raspar LinkedIn ou Gupy."""
    secret = os.getenv("SERPER_API_KEY")
    if not secret: raise RuntimeError("SERPER_API_KEY não configurada")
    out = []
    for domain in ("site:linkedin.com/jobs/view", "site:gupy.io/jobs", "site:indeed.com.br/viewjob", "site:remotar.com.br/job", "site:jobs.lever.co", "site:boards.greenhouse.io"):
        for term in SEARCHES[:]:
            data = fetch_json("https://google.serper.dev/search", method="POST",
                payload={"q":domain+" "+term, "gl":"br","hl":"pt-br","num":10,"tbs":"qdr:m"},
                headers={"X-API-KEY":secret,"Content-Type":"application/json"})
            for row in data.get("organic", []):
                link=row.get("link") or ""
                title=clean(row.get("title"))
                descr=clean(row.get("snippet"))
                if not link.startswith("https://"): continue
                if not any(k in norm(title+" "+descr) for k in ("remot", "home office", "teletrabalho")): continue
                company = clean(title.split(" - ")[-1].split(" | ")[-1])
                if company==title: company="Empresa a confirmar"
                j=job(title, company, descr, link, "Busca indexada "+domain[5:], 
                      "indicado no resultado; validar no anúncio", "", "", "")
                if j: out.append(j)
    return out

def fingerprint(j):
    return norm(j["company"]) + "|" + norm(j["title"])

def evaluate(j):
    title, desc = norm(j["title"]), norm(j["description"])
    if any(norm(x) in desc for x in HARD_BLOCK): return None
    cat = j["category"]
    # 35 pontos pela experiência relevante, 25 requisitos técnicos, 15 remoto,
    # 15 regime/senioridade, 10 interesse. Notas são aproximadas, não 91 fixo.
    exp = min(35, 17 + 3*sum(1 for w in POSITIVE[cat] if norm(w) in desc))
    tech = min(25, 8 + 3*sum(1 for w in POSITIVE[cat] if norm(w) in title+" "+desc))
    remote = 15 if "compatível" in j["remote"] or "geografia" in j["remote"] else 8
    seniority = 10 if any(k in title for k in ("senior","senior","sr","gerente","manager","consultor","especialista")) else 8
    if any(w in norm(j["regime"]) for w in ("full time", "tempo integral", "clt")): seniority += 3
    goals = {"Docência e tutoria":10,"Consultoria":9,"Gestão e governança TI":10,"Dados e negócios":9,"IA e ciência de dados":7,"Administração tecnológica":8}[cat]
    penalty = 0
    notes = []
    if any(x in desc for x in ENGLISH_STRONG):
        penalty += 22
        notes.append("exige inglês fluente/avançado: requisito potencialmente eliminatório")
    elif any(x in desc for x in ENGLISH_MID):
        penalty += 12
        notes.append("inglês avançado indicado")
    elif len(re.findall(r"\b(the|and|experience|required|with|you|will|work)\b",desc)) >= 5:
        penalty += 7
        notes.append("anúncio em inglês; proficiência a confirmar")
    else:
        notes.append("anúncio em português ou idioma não determinado")
    if "validar" in j["remote"]: notes.append("remoto ainda não confirmado no texto integral")
    score = max(0,min(99,exp+tech+remote+seniority+goals-penalty))
    return score, "; ".join(notes)

def salary_text(j):
    if j["salary"]:
        return "Salário anunciado: "+j["salary"]+" (confirmar moeda/período na vaga)"
    cat = j["category"]
    value,label,url = BENCHMARK[cat]
    amount = f"R$ {value:,.0f}".replace(",","X").replace(".",",").replace("X",".")
    return (f"Referência de mercado: {amount}/mês, média salarial base CLT Brasil, "
            f"{label}, dados CAGED divulgados em 08/10/2026. NÃO é salário oferecido"
            f" e não é estimativa PJ. Fonte: {url}")

def report(jobs,sources):
    lines = ["RADAR DE OPORTUNIDADES — "+now().strftime("%d/%m/%Y"), "",
             "Triagem preliminar; cargos e requisitos devem ser validados no anúncio.",
             "Preferência: remoto Brasil, português, CLT; PJ, contratos e docência incluídos.", ""]
    if not jobs: lines.append("Nenhuma vaga NOVA elegível foi identificada nas fontes acessíveis.")
    for cat in CATEGORIES:
        group=[j for j in jobs if j["category"]==cat]
        if not group: continue
        lines += [cat.upper(),"="*34]
        for j in group:
            lines += [f"{j['score']}/100 | {j['title']} | {j['company']}",
                      f"Origem: {j['source']} | Modalidade: {j['remote']} | Contrato: {j['regime']} | Publicação: {j['date']}",
                      "Avaliação de idioma: "+j["notes"], "Remuneração: "+salary_text(j),
                      "Candidatura: "+j["url"], ""]
    lines += ["COBERTURA DAS FONTES", *sources,
              "LinkedIn/Gupy: resultados indexados apenas quando há SERPER_API_KEY.",
              "Fontes de salário: Portal Salário/CAGED, valores de referência por categoria e não da vaga.",
              "Não há candidatura automática nem garantia de elegibilidade; confira o anúncio original."]
    return "\n".join(lines)

def email(report_text):
    account=os.getenv("GMAIL_USER")
    password=os.getenv("GMAIL_APP_PASSWORD")
    if not account or not password: raise RuntimeError("Credenciais Gmail ausentes")
    m=EmailMessage()
    m["From"]=account; m["To"]=TO
    m["Subject"]="Radar de oportunidades remotas — "+now().strftime("%d/%m/%Y")
    m.set_content(report_text)
    with smtplib.SMTP_SSL("smtp.gmail.com",465, timeout=45, context=ssl.create_default_context()) as smtp:
        smtp.login(account,password); smtp.send_message(m)

def main():
    state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"seen":INITIAL_SEEN, "last_email_date":""}
    today=now().strftime("%Y-%m-%d")
    if state.get("last_email_date")==today:
        print("Já houve envio hoje; use uma nova data para novo relatório.")
        return
    sources, found, ok = [], [], 0
    for name,fn in (("Remotive",remotive),("Himalayas",himalayas),("Jobicy",jobicy),("Google indexado (LinkedIn/Gupy/Indeed/Remotar/Lever/Greenhouse)",serper_indexed)):
        try:
            jobs=fn()
            found.extend(jobs); sources.append(f"{name}: {len(jobs)} candidatos")
            ok += 1
        except Exception as exc:
            sources.append(f"{name}: não acessível ({type(exc).__name__}: {str(exc)[:90]})")
    if not ok: raise RuntimeError("Nenhuma fonte acessível; não enviar relatório vazio.")
    seen=set(state.get("seen",[]))
    chosen=[]
    for j in found:
        k=fingerprint(j)
        if k in seen: continue
        val=evaluate(j)
        if val is None or val[0]<65: continue
        j["score"],j["notes"]=val
        seen.add(k); chosen.append(j)
    chosen.sort(key=lambda j:(-j["score"],j["source"],j["company"]))
    chosen=chosen[:35]
    payload=report(chosen,sources)
    print("Fontes:",sources,"Selecionadas:",len(chosen))
    email(payload)
    state["seen"]=sorted(set(state.get("seen",[])) | {fingerprint(j) for j in chosen})
    state["last_email_date"]=today
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Envio SMTP confirmado; histórico atualizado.")

if __name__=="__main__":
    main()
