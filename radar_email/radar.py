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
    "Suporte técnico e aplicações": ("analista de suporte", "tecnico de suporte", "técnico de suporte", "suporte técnico", "suporte de sistemas", "suporte a aplicações", "suporte n1", "suporte n2", "suporte n3", "help desk", "service desk", "technical support", "application support", "support analyst", "support engineer", "it support"),
    "Freelancer e projetos": ("freelancer", "freelance", "projeto pontual", "prestação de serviços"),
}
POSITIVE = {
    "Freelancer e projetos": ("python", "sql", "power bi", "dashboard", "automacao", "automação", "ia", "chatbot", "data", "consultoria", "site", "treinamento", "etl", "excel", "itil", "projeto"),
    "Docência e tutoria": ("treinamento", "curso", "educa", "ensino", "training", "instructor", "tutor", "computing", "technology"),
    "Consultoria": ("implant", "process", "projeto", "project", "itil", "consult", "cliente", "client", "business", "sistema"),
    "Gestão e governança TI": ("itil", "sla", "service", "project", "governance", "governança", "observability", "gestão", "process", "kpi", "management"),
    "Dados e negócios": ("sql", "power bi", "python", "pandas", "etl", "dashboard", "analytics", "business"),
    "IA e ciência de dados": ("python", "machine learning", "deep learning", "data", "analytics", "scikit", "statistic", "time series"),
    "Administração tecnológica": ("process", "operations", "gestão", "itil", "sla", "service", "coordination"),
    "Suporte técnico e aplicações": ("itil", "sla", "service desk", "help desk", "troubleshooting", "windows", "linux", "suporte", "incidente", "incident", "sql", "sistema", "application", "customer", "ticket"),
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

def job(title, company, desc, url, source, remote, regime="", date="", salary="", force_category=None):
    title, company, desc = clean(title), clean(company), clean(desc)
    if not title or not company or not url.startswith("https://"):
        return None
    cat = force_category or category(title)
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
    for term in ("project manager", "data analyst", "consultant", "instructor", "data scientist", "business analyst", "technical support", "service desk"):
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
    """Pesquisa resultados indexados de plataformas de emprego via Serper."""
    secret = os.getenv("SERPER_API_KEY")
    if not secret:
        raise RuntimeError("SERPER_API_KEY não configurada")
    plan = {
        "LinkedIn": ("site:linkedin.com/jobs/view/", [
            '"gerente de projetos" remoto Brasil', '"gestão de serviços" remoto',
            '"analista de negócios" remoto', '"analista de dados" remoto',
            '"professor" tecnologia remoto', '"consultor TI" remoto', '"analista de suporte" remoto', '"service desk" remoto meio período', '"suporte N2" remoto']),
        "Gupy": ("site:gupy.io/jobs/", [
            '"gestão de TI" remoto', '"analista de dados" remoto',
            '"consultor" implantação remoto', '"tutor" EAD remoto',
            '"governança" remoto', '"Power BI" remoto', '"analista de suporte" remoto', '"suporte de sistemas" remoto', '"suporte técnico" home office']),
        "Glassdoor": ("site:glassdoor.com.br/Job/", [
            '"analista de dados" remoto', '"gerente de projetos" remoto',
            '"consultor de TI" remoto', '"professor tecnologia" remoto', '"help desk" remoto', '"suporte técnico" meio período remoto']),
        "Indeed": ("site:br.indeed.com/viewjob", [
            '"gerente de projetos" remoto', '"analista de negócios" remoto', '"suporte técnico" remoto meio período']),
        "Remotar": ("site:remotar.com.br/job/", [
            '"gerente" TI', '"analista de dados"']),
        "Carreiras corporativas": ("(site:jobs.lever.co OR site:job-boards.greenhouse.io)", [
            '"Brazil" "remote" "project manager"', '"Brasil" "remoto" "analista"']),
    }
    out = []
    for source, (domain, terms) in plan.items():
        for term in terms:
            data = fetch_json("https://google.serper.dev/search", method="POST",
                payload={"q": domain+" "+term, "gl":"br", "hl":"pt-br",
                         "num":10, "tbs":"qdr:m"},
                headers={"X-API-KEY":secret,"Content-Type":"application/json"})
            for row in data.get("organic", []):
                link = row.get("link") or ""
                title = clean(row.get("title"))
                desc = clean(row.get("snippet"))
                text = norm(title+" "+desc)
                if not link.startswith("https://"): continue
                if not any(w in text for w in ("remoto","remota","remote","home office","teletrabalho")): continue
                if any(w in (" " + text + " ") for w in (" hibrido ", " hibrida ", " presencial ", " hybrid ", " onsite ", " on site ")): continue
                # O resultado indexado não garante que a vaga continue aberta.
                title = re.split(r"\s+[|–-]\s+(?:LinkedIn|Gupy|Indeed|Glassdoor)\b",title)[0].strip()
                company = "Empresa a confirmar"
                j = job(title,company,desc,link,"Busca indexada: "+source,
                        "remoto indicado no índice; validar anúncio")
                if j: out.append(j)
    return list({j["url"].split("?")[0]: j for j in out}.values())

# Plataformas de prestação de serviços: consulta somente anúncios públicos indexados.
# SimplyHired e Jooble são buscadores de empregos, não marketplaces de projetos.
FREELANCE_SOURCES = {
    "99Freelas": ("site:99freelas.com.br/project/", ('"python" "projeto"','"power bi" dashboard','"automação" excel')),
    "Workana": ("site:workana.com/job/", ('"python" dados','"power bi" dashboard','"inteligência artificial" automação')),
    "Freelancer.com.br": ("site:freelancer.com/projects/", ('"python" portuguese','"dashboard" "power bi"')),
    "Vinteconto": ("site:vinteconto.com.br/", ('"projetos em aberto" tecnologia','"projeto" dashboard')),
    "Fiverr": ("site:fiverr.com/", ('"buyer request" python automation','"brief" data analysis')),
    "GetNinjas": ("site:getninjas.com.br/", ('"pedido" "aulas de informática"','"consultoria" "tecnologia"')),
    "SimplyHired": ("site:br.simplyhired.com/job/", ('"freelancer" "python" remoto','"consultor" remoto projeto')),
    "Jooble": ("site:br.jooble.org/jdp/", ('"freelancer" "power bi" remoto','"consultor" projeto remoto')),
}
FREELANCE_SKILLS = (
    "python", "sql", "power bi", "dashboard", "dados", "analise", "análise",
    "automacao", "automação", "excel", "chatbot", "inteligencia artificial",
    "inteligência artificial", "machine learning", "curso", "treinamento",
    "itil", "consultoria de ti", "site", "etl", "api", "business intelligence"
)

def freelance_indexed():
    secret = os.getenv("SERPER_API_KEY")
    if not secret:
        raise RuntimeError("SERPER_API_KEY não configurada")
    out = {}
    for source, (domain, terms) in FREELANCE_SOURCES.items():
        for term in terms:
            data = fetch_json("https://google.serper.dev/search", method="POST",
                payload={"q":domain+" "+term,"gl":"br","hl":"pt-br","num":10,"tbs":"qdr:m"},
                headers={"X-API-KEY":secret,"Content-Type":"application/json"})
            for row in data.get("organic",[]):
                link = row.get("link") or ""
                title = clean(row.get("title"))
                desc = clean(row.get("snippet"))
                raw = norm(title+" "+desc)
                if not link.startswith("https://") or not any(norm(w) in raw for w in FREELANCE_SKILLS):
                    continue
                if any(w in " "+raw+" " for w in (" presencial ", " hibrido ", " hibrida ", " hybrid ", " onsite ")):
                    continue
                parsed = urllib.parse.urlsplit(link)
                path = parsed.path.lower()
                # Remover páginas de freelancers que oferecem serviços e landing pages.
                if source == "99Freelas" and "/project/" not in path: continue
                if source == "Workana" and "/job/" not in path: continue
                if source == "Freelancer.com.br" and "/projects/" not in path: continue
                if source == "SimplyHired" and "/job/" not in path: continue
                if source == "Jooble" and "/jdp/" not in path: continue
                if source in ("Vinteconto","Fiverr","GetNinjas"):
                    # Essas fontes em geral expõem catálogos de prestadores,
                    # não demandas verificáveis; não transformar catálogo em vaga.
                    if not any(x in raw for x in ("preciso de freelancer","projeto em aberto","contratar freelancer","solicito proposta")):
                        continue
                # Remoto é inerente a várias tarefas digitais, mas precisa
                # ser validado com o contratante antes da candidatura.
                j = job(title, "Contratante via "+source,desc,link,
                        "Freelancer: "+source,
                        "trabalho digital; confirmar execução 100% remota",
                        regime="Projeto/serviço",force_category="Freelancer e projetos")
                if j:
                    out[canonical_url(link)] = j
    return list(out.values())

def fingerprint(j):
    if j["category"] == "Freelancer e projetos" or j["company"] == "Empresa a confirmar":
        return "url|" + canonical_url(j["url"])
    return norm(j["company"]) + "|" + norm(j["title"])

def canonical_url(url):
    parts = urllib.parse.urlsplit(url)
    return parts.netloc.lower().removeprefix("www.") + parts.path.rstrip("/").lower()

def evaluate(j):
    title, desc = norm(j["title"]), norm(j["description"])
    if any(norm(x) in desc for x in HARD_BLOCK): return None
    cat = j["category"]
    # Busca indexada: texto curto não permite medir requisitos detalhadamente.
    # Criar faixa preliminar própria (65-79), SEM declarar elegibilidade confirmada.
    indexed = j["source"].startswith("Busca indexada:")
    hits = sum(1 for w in POSITIVE[cat] if norm(w) in title+" "+desc)
    if indexed:
        exp = min(35, 26 + min(6, 2*hits))
        tech = min(25, 15 + min(6, 2*hits))
        remote = 8
        seniority = 8
    else:
        exp = min(35, 17 + 3*sum(1 for w in POSITIVE[cat] if norm(w) in desc))
        tech = min(25, 8 + 3*hits)
        remote = 15 if "compatível" in j["remote"] or "geografia" in j["remote"] else 7
        seniority = 10 if any(k in title for k in ("senior","sr","gerente","manager","consultor","especialista")) else 8
        if any(w in norm(j["regime"]) for w in ("full time", "tempo integral", "clt")):
            seniority += 3
    goals = {"Suporte técnico e aplicações":9,"Freelancer e projetos":10,"Docência e tutoria":10,"Consultoria":9,"Gestão e governança TI":10,"Dados e negócios":9,"IA e ciência de dados":7,"Administração tecnológica":8}[cat]
    penalty = 0
    notes = []
    if any(norm(x) in desc for x in ENGLISH_STRONG):
        penalty += 18
        notes.append("exige inglês fluente/avançado: requisito potencialmente eliminatório")
    elif any(norm(x) in desc for x in ENGLISH_MID):
        penalty += 10
        notes.append("inglês avançado indicado")
    elif len(re.findall(r"\b(the|and|experience|required|with|you|will|work)\b",desc)) >= 5:
        penalty += 5
        notes.append("anúncio em inglês; proficiência a confirmar")
    else:
        notes.append("anúncio em português ou idioma não determinado")
    if "validar" in j["remote"] or "confirmar" in j["remote"]: notes.append("remoto ainda não confirmado; validar antes de propor")
    if schedule_info(j)[0] in ("MEIO PERÍODO", "HORÁRIO FLEXÍVEL", "HORÁRIO ALTERNATIVO"):
        goals += 5
    score = max(0,min(79 if indexed else 99,exp+tech+remote+seniority+goals-penalty))
    if indexed:
        notes.append("PRÉ-TRIAGEM: descrição indexada incompleta; requisitos, empresa e remoto precisam ser confirmados")
    return score, "; ".join(notes)

PART_TIME = ("meio periodo", "tempo parcial", "part time", "part-time", "20 horas semanais", "24 horas semanais", "30 horas semanais", "4 horas por dia", "6 horas por dia")
FLEXIBLE = ("horario flexivel", "horarios flexiveis", "flexible hours", "flexible schedule", "horarios a combinar", "horario a combinar", "escolha seu horario", "choose your hours")
ALTERNATIVE = ("turno noturno", "turno da noite", "periodo noturno", "turno vespertino", "fins de semana", "escala 12x36", "night shift", "evening shift", "weekend shift", "overnight shift")
ROTATING = ("escala de revezamento", "turnos rotativos", "rotating shift", "shift work")
FULL_TIME = ("tempo integral", "full time", "full-time", "40 horas semanais", "44 horas semanais")

def schedule_info(j):
    """Sinalização conservadora: só classifica com evidência textual."""
    txt = norm(j["title"] + " " + j["description"] + " " + j["regime"])
    def has(terms):
        return any(norm(term) in txt for term in terms)
    if has(PART_TIME):
        return ("MEIO PERÍODO", "Jornada parcial indicada; confirmar carga horária")
    if has(FLEXIBLE):
        return ("HORÁRIO FLEXÍVEL", "Flexibilidade indicada; confirmar disponibilidade exigida")
    if has(ALTERNATIVE):
        return ("HORÁRIO ALTERNATIVO", "Turno alternativo indicado; confirmar dias e horários")
    if has(ROTATING):
        return ("ESCALA A CONFIRMAR", "Turnos citados, sem garantia de compatibilidade")
    if has(FULL_TIME):
        return ("TEMPO INTEGRAL", "Jornada integral indicada")
    return ("NÃO INFORMADO", "Carga horária não identificada no texto disponível")

def salary_text(j):
    if j["category"] == "Freelancer e projetos":
        return ("Orçamento anunciado: " + j["salary"] + " (validar no projeto)" if j["salary"] else "Orçamento não divulgado; sem média verificável comparável por projeto.")
    if j["salary"]:
        return "Salário anunciado: "+j["salary"]+" (confirmar moeda/período na vaga)"
    cat = j["category"]
    if cat not in BENCHMARK:
        return "Salário não divulgado; referência brasileira comparável não identificada para esta função."
    value,label,url = BENCHMARK[cat]
    amount = f"R$ {value:,.0f}".replace(",","X").replace(".",",").replace("X",".")
    return (f"Referência de mercado: {amount}/mês, média salarial base CLT Brasil, "
            f"{label}, dados CAGED divulgados em 08/10/2026. NÃO é salário oferecido"
            f" e não é estimativa PJ. Fonte: {url}")

RADAR_PUBLIC_URL = "https://alvarobonifacio1980.github.io/alvarobonifacio1980/radar/"
PUBLIC_RADAR_HTML = ROOT.parent / "docs" / "radar" / "index.html"

MAX_TOTAL_JOBS = 500

def published_timestamp(raw):
    """Converte data da fonte em instante UTC; datas ausentes/invalidas ficam por ultimo."""
    value = str(raw or "").strip()
    if not value or value.lower() in ("nao informada", "não informada"):
        return -1.0
    try:
        if re.fullmatch(r"\d{10}(?:\.\d+)?", value):
            return float(value)
        if re.fullmatch(r"\d{13}", value):
            return int(value) / 1000
        for pattern in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                pass
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, OverflowError, OSError):
        return -1.0

def formatted_date(raw):
    timestamp = published_timestamp(raw)
    if timestamp < 0:
        return "não informada"
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%d/%m/%Y")
    except (ValueError, OverflowError, OSError):
        return "não informada"

def ordered_jobs(jobs):
    """Ordem por categoria; dentro de cada grupo: nota desc, data desc, desempate estavel."""
    grouped = []
    for name in CATEGORIES:
        items = [j for j in jobs if j["category"] == name]
        items.sort(key=lambda j: (-int(j["score"]), -published_timestamp(j.get("date")),
                                  norm(j.get("company")), norm(j.get("title"))))
        grouped.extend(items)
    return grouped[:MAX_TOTAL_JOBS]

def alignment_reasons(j):
    """Explicação baseada apenas nas evidências identificadas pela triagem."""
    cat = j["category"]
    title = norm(j["title"])
    desc = norm(j["description"])
    source_indexed = j["source"].startswith("Busca indexada:")
    strong, caution = [], []
    hits = []
    for term in POSITIVE[cat]:
        normalized = norm(term)
        if len(normalized) < 3 or normalized in ("data", "site", "ia", "api"):
            continue
        if normalized in title + " " + desc and normalized not in hits:
            hits.append(normalized)
    strong.append("Cargo alinhado à área de " + cat.lower())
    if hits:
        strong.append("Termos técnicos relacionados ao perfil: " + ", ".join(hits[:4]))
    shift = schedule_info(j)[0]
    if shift in ("MEIO PERÍODO", "HORÁRIO FLEXÍVEL", "HORÁRIO ALTERNATIVO"):
        strong.append("Jornada potencialmente conciliável: " + shift.lower())
    if j.get("salary"):
        strong.append("Remuneração ou orçamento informado no anúncio")
    if source_indexed:
        caution.append("Resumo indexado: requisitos detalhados e empresa ainda precisam de confirmação")
    if "validar" in j["remote"] or "confirmar" in j["remote"]:
        caution.append("Modalidade 100% remota não verificada no anúncio completo")
    if shift == "NÃO INFORMADO":
        caution.append("Carga horária não informada")
    elif shift == "ESCALA A CONFIRMAR":
        caution.append("Escala de trabalho precisa ser confirmada")
    elif shift == "TEMPO INTEGRAL":
        caution.append("Jornada integral pode dificultar a conciliação com o mestrado")
    notes = j.get("notes", "")
    if "exige inglês fluente" in notes:
        caution.append("Exigência de inglês fluente/avançado; confirmar nível requerido")
    elif "inglês avançado" in notes:
        caution.append("Inglês avançado citado; confirmar requisito")
    elif "anúncio em inglês" in notes:
        caution.append("Anúncio em inglês; exigência de fluência ainda não determinada")
    if not hits:
        caution.append("Competências técnicas não detalhadas no texto disponível")
    if not j.get("salary"):
        caution.append("Remuneração da oportunidade não divulgada")
    return strong[:4], caution[:4]


def report(jobs,sources):
    lines = ["RADAR DE OPORTUNIDADES — "+now().strftime("%d/%m/%Y"), "",
             "Triagem preliminar; cargos e requisitos devem ser validados no anúncio.",
             "Preferência: remoto Brasil, português, CLT; PJ, contratos e docência incluídos.",
             "Destaque para meio período e horários alternativos; jornada ausente não é presumida.", ""]
    if not jobs: lines.append("Nenhuma vaga NOVA elegível foi identificada nas fontes acessíveis.")
    for cat in CATEGORIES:
        group=[j for j in jobs if j["category"]==cat]
        if not group: continue
        lines += [cat.upper(),"="*34]
        for j in group:
            destaque = "[CONCILIAÇÃO MESTRADO] " if schedule_info(j)[0] in ("MEIO PERÍODO", "HORÁRIO FLEXÍVEL", "HORÁRIO ALTERNATIVO") else ""
            lines += [f"{destaque}{j['score']}/100 | {j['title']} | {j['company']}",
                      f"Origem: {j['source']} | Modalidade: {j['remote']} | Contrato: {j['regime']} | Publicação: {formatted_date(j['date'])}",
                      "Jornada: "+schedule_info(j)[0]+" — "+schedule_info(j)[1],
                      "Pontos favoráveis: "+"; ".join(alignment_reasons(j)[0]),
                      "Pontos de atenção: "+"; ".join(alignment_reasons(j)[1]),
                      "Avaliação de idioma: "+j["notes"], "Remuneração: "+salary_text(j),
                      "Candidatura: "+j["url"], ""]
    lines += ["COBERTURA DAS FONTES", *sources,
              "LinkedIn/Gupy: resultados indexados apenas quando há SERPER_API_KEY.",
              "Fontes de salário: Portal Salário/CAGED, valores de referência por categoria e não da vaga.",
              "Não há candidatura automática nem garantia de elegibilidade; confira o anúncio original."]
    return "\n".join(lines)


def render_html(jobs, sources, preview=False, include_seen=False, interactive=False):
    """HTML para Gmail e prévia local. Usa estilos inline e URLs validadas."""
    esc = lambda value: html.escape(str(value or ""), quote=True)
    def safe_link(url):
        parts = urllib.parse.urlsplit(str(url or ""))
        if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
            return ""
        return esc(url)
    good_shifts = {"MEIO PERÍODO", "HORÁRIO FLEXÍVEL", "HORÁRIO ALTERNATIVO"}
    count_brazil = sum(j["source"].startswith("Busca indexada:") for j in jobs)
    count_freelance = sum(j["category"] == "Freelancer e projetos" for j in jobs)
    count_other = len(jobs) - count_brazil - count_freelance
    counts = (
        ("Portais nacionais", count_brazil),
        ("Internacionais", count_other),
        ("Freelancer", count_freelance),
    )
    pieces = [
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>',
        '<body style="margin:0;background:#f3f5f9;color:#17253d;font-family:Arial,Helvetica,sans-serif">',
        '<div style="display:none;max-height:0;overflow:hidden;color:transparent">Vagas remotas, jornada e aderência ao currículo.</div>',
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f3f5f9"><tr><td align="center" style="padding:20px 10px">',
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width:740px;background:#ffffff;border-radius:12px">',
        '<tr><td style="background:#172c4d;color:#ffffff;padding:27px 24px;border-radius:12px 12px 0 0">',
        '<div style="font-size:12px;letter-spacing:2px;color:#b9cce9;font-weight:bold">RADAR DE CARREIRA</div>',
        '<h1 style="font-size:25px;line-height:1.2;margin:10px 0 6px;color:#ffffff">Oportunidades remotas</h1>',
        '<div style="font-size:14px;color:#d6e3f3">'+esc(now().strftime("%d/%m/%Y"))+'</div></td></tr>',
    ]
    if preview:
        mode = "Demonstração, inclusive vagas já apresentadas" if include_seen else "Somente vagas ainda não apresentadas"
        pieces += ['<tr><td style="padding:15px 24px;background:#fff4de;color:#684510;font-size:13px">',
                   '<strong>PRÉVIA — NÃO ENVIADA E NÃO REGISTRADA.</strong> '+esc(mode)+'. Pesquisa atual, não cópia de um e-mail anterior.</td></tr>']
    pieces.append('<tr><td style="padding:20px 24px 10px">'
                  '<p style="margin:0 0 14px;font-size:14px;color:#46556c">'
                  'Prioridade para vagas brasileiras em português, trabalho remoto e oportunidades conciliáveis com o mestrado. '
                  'Notas são triagens preliminares; confirme os requisitos no anúncio.</p>'
                  '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>')
    for label, number in counts:
        pieces.append('<td style="padding:8px;border:1px solid #e5e9f0;text-align:center">'
                      '<div style="font-size:23px;font-weight:bold;color:#172c4d">'+str(number)+'</div>'
                      '<div style="font-size:11px;color:#65758c">'+esc(label)+'</div></td>')
    pieces.append('</tr></table></td></tr>')
    if not interactive:
        pieces.append('<tr><td style="padding:8px 24px 18px;text-align:center">'
                      '<a href="'+esc(RADAR_PUBLIC_URL)+'" '
                      'style="display:inline-block;background:#176744;color:#ffffff;text-decoration:none;'
                      'padding:14px 20px;border-radius:8px;font-size:15px;font-weight:bold">'
                      'Abrir radar com filtros no navegador</a>'
                      '<div style="font-size:12px;color:#65758c;padding-top:8px">'
                      'Filtre por nota, fonte, data, área e conciliação com o mestrado.</div>'
                      '</td></tr>')
    if not jobs:
        pieces.append('<tr><td style="padding:20px 24px;color:#53627a">Nenhuma vaga nova elegível identificada nas fontes acessíveis.</td></tr>')
    if interactive:
        source_options = sorted(set(j["source"] for j in jobs))
        pieces.append('<tr><td style="padding:10px 24px 20px"><div role="group" aria-label="Filtros de oportunidades" '
                      'style="padding:14px;background:#edf3fb;border-radius:8px">'
                      '<strong style="display:block;margin-bottom:10px">Filtrar oportunidades</strong>'
                      '<label>Conciliação <select id="f-conc"><option value="">Todas</option><option value="sim">Meio período / flexível / alternativo</option></select></label> '
                      '<label>Fonte <select id="f-source"><option value="">Todas as fontes</option>')
        for src in source_options:
            pieces.append('<option value="'+esc(src)+'">'+esc(src)+'</option>')
        pieces.append('</select></label> <label>Nota mínima <input id="f-score" type="number" min="0" max="100" '
                      'value="0" style="width:55px"></label> '
                      '<label>Publicação <select id="f-date"><option value="0">Qualquer data</option>'
                      '<option value="7">Últimos 7 dias</option><option value="30">Últimos 30 dias</option></select></label> '
                      '<label>Área <select id="f-cat"><option value="">Todas as áreas</option>')
        for cat in CATEGORIES:
            pieces.append('<option value="'+esc(cat)+'">'+esc(cat)+'</option>')
        pieces.append('</select></label> '
                      '<button type="button" id="f-reset">Limpar filtros</button>'
                      '<div id="f-count" aria-live="polite" style="padding-top:9px;font-size:12px"></div>'
                      '</div></td></tr>')
    else:
        pieces.append('<tr><td style="padding:10px 24px 14px;color:#526584;font-size:12px">'
                      'Navegue pelas áreas abaixo. Para aplicar filtros interativos, abra o arquivo HTML '
                      'do relatório no navegador.</td></tr>')
    for cat in CATEGORIES:
        group = [j for j in jobs if j["category"] == cat]
        if not group:
            continue
        pieces.append('<tr data-section="'+esc(cat)+'"><td style="padding:21px 24px 8px">'
                      '<h2 style="font-size:17px;margin:0;color:#172c4d;border-bottom:2px solid #d9e5f2;padding-bottom:9px">'
                      +esc(cat)+'</h2></td></tr>')
        for j in group:
            shift, explanation = schedule_info(j)
            preferred = shift in good_shifts
            score = max(0, min(100, int(j["score"])))
            score_label = f"{score}/100" + (" · Pré-triagem" if j["source"].startswith("Busca indexada:") else "")
            link = safe_link(j["url"])
            date = published_timestamp(j.get("date"))
            attrs = (' data-card="1" data-category="'+esc(cat)+'" data-source="'+esc(j["source"])+
                     '" data-score="'+str(score)+'" data-date="'+str(int(date) if date >= 0 else -1)+
                     '" data-conc="'+("sim" if preferred else "nao")+'"')
            pieces.append('<tr'+attrs+'><td style="padding:8px 24px 14px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                          'style="border:1px solid #e0e6ee;border-radius:9px"><tr><td style="padding:16px 16px 17px">')
            if preferred:
                pieces.append('<div style="font-size:11px;font-weight:bold;color:#176744;background:#e8f5ed;padding:6px 9px;display:inline-block;border-radius:4px;margin-bottom:9px">'
                              '★ CONCILIAÇÃO MESTRADO</div>')
            pieces.append('<div style="font-size:13px;color:#42618a;font-weight:bold">'+esc(score_label)+'</div>')
            good, weak = alignment_reasons(j)
            pieces.append('<div style="font-size:12px;line-height:1.45;padding:8px 0 11px">'
                          '<div style="color:#176744"><strong>Pontos fortes:</strong> '+esc("; ".join(good))+'</div>'
                          '<div style="color:#895d25;margin-top:5px"><strong>Pontos de atenção:</strong> '+
                          esc("; ".join(weak))+'</div></div>')
            pieces.append('<h3 style="font-size:17px;line-height:1.3;margin:7px 0 4px;color:#172c4d">'+esc(j["title"])+'</h3>')
            pieces.append('<div style="font-size:14px;color:#3e516e;margin-bottom:12px">'+esc(j["company"])+'</div>')
            fields = (
                ("Fonte",j["source"]), ("Jornada",shift+" — "+explanation),
                ("Modalidade",j["remote"]),("Regime",j["regime"]),
                ("Publicação",formatted_date(j["date"])),("Idioma e ressalvas",j.get("notes","")),
                ("Remuneração / orçamento",salary_text(j)),
            )
            for label, value in fields:
                is_shift = label == "Jornada" and preferred
                color = "#176744" if is_shift else "#4c5870"
                pieces.append('<div style="font-size:12px;line-height:1.55;color:'+color+';padding:2px 0">'
                              '<strong>'+esc(label)+':</strong> '+esc(value)+'</div>')
            if link:
                pieces.append('<div style="padding-top:15px">'
                              '<a href="'+link+'" style="background:#2456a6;color:#ffffff;text-decoration:none;'
                              'padding:11px 16px;border-radius:6px;font-size:13px;font-weight:bold;display:inline-block">'
                              'Ver oportunidade</a></div>')
            pieces.append('</td></tr></table></td></tr>')
    pieces.append('<tr><td style="padding:16px 24px 24px;border-top:1px solid #e1e7ef">'
                  '<h2 style="font-size:15px;margin:0 0 9px">Cobertura das fontes</h2>')
    for item in sources:
        pieces.append('<div style="font-size:12px;line-height:1.55;color:#53627a">'+esc(item)+'</div>')
    pieces.append('<p style="font-size:12px;color:#6b7485;line-height:1.55;margin:13px 0 0">'
                  'Vagas indexadas podem estar desatualizadas. O remoto e a compatibilidade de requisitos precisam ser confirmados. '
                  'As médias salariais são referências por ocupação, não ofertas das empresas. '
                  'Este relatório não realiza candidaturas automaticamente.</p>'
                  '</td></tr></table></td></tr></table></body></html>')
    if interactive:
        # O JS fica SOMENTE no arquivo aberto no navegador; nunca no corpo do Gmail.
        script = """<script>
(function () {
 const $=id=>document.getElementById(id);
 const cards=[...document.querySelectorAll('[data-card]')];
 const update=()=>{
   const conc=$('f-conc').value,src=$('f-source').value,score=Number($('f-score').value||0);
   const days=Number($('f-date').value||0),cat=$('f-cat').value;
   const today=Math.floor(Date.now()/1000);let shown=0;
   cards.forEach(row=>{
     const date=Number(row.dataset.date);
     const visible=(!conc||row.dataset.conc===conc) && (!src||row.dataset.source===src)
       && Number(row.dataset.score)>=score && (!cat||row.dataset.category===cat)
       && (!days||(date>=0 && date>=today-days*86400 && date<=today+86400));
     row.style.display=visible?'':'none';if(visible)shown++;
   });
   document.querySelectorAll('[data-section]').forEach(row=>{
     row.style.display=cards.some(c=>c.dataset.category===row.dataset.section&&c.style.display!=='none')?'':'none';
   });
   $('f-count').textContent=shown+' de '+cards.length+' oportunidades exibidas';
 };
 ['f-conc','f-source','f-score','f-date','f-cat'].forEach(id=>{
   $(id).addEventListener('input',update);$(id).addEventListener('change',update);
 });
 $('f-reset').addEventListener('click',()=>{
   ['f-conc','f-source','f-cat'].forEach(id=>$(id).value='');
   $('f-score').value='0';$('f-date').value='0';update();
 });
 update();
})();
</script>"""
        pieces.insert(-1, script)
    return "".join(pieces)

def email(report_text, report_html):
    account=os.getenv("GMAIL_USER")
    password=os.getenv("GMAIL_APP_PASSWORD")
    if not account or not password: raise RuntimeError("Credenciais Gmail ausentes")
    m=EmailMessage()
    m["From"]=account; m["To"]=TO
    m["Subject"]="Radar de oportunidades remotas — "+now().strftime("%d/%m/%Y")
    m.set_content(report_text)
    m.add_alternative(report_html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com",465, timeout=45, context=ssl.create_default_context()) as smtp:
        smtp.login(account,password); smtp.send_message(m)

def main():
    state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"seen":INITIAL_SEEN, "last_email_date":""}
    today=now().strftime("%Y-%m-%d")
    preview = os.getenv("RADAR_PREVIEW", "").strip().lower() == "true"
    include_seen = preview and os.getenv("PREVIEW_INCLUDE_SEEN", "").strip().lower() == "true"
    if state.get("last_email_date")==today and not preview:
        print("Já houve envio hoje; não enviar novamente.")
        return
    sources, found, ok = [], [], 0
    for name,fn in (("Remotive",remotive),("Himalayas",himalayas),("Jobicy",jobicy),("Google indexado (LinkedIn/Gupy/Glassdoor/Indeed/Remotar/Lever/Greenhouse)",serper_indexed),("Freelancers (99Freelas/Workana/Freelancer/Vinteconto/Fiverr/GetNinjas/SimplyHired/Jooble)",freelance_indexed)):
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
        if k in seen and not include_seen: continue
        val=evaluate(j)
        if val is None or val[0]<65: continue
        j["score"],j["notes"]=val
        seen.add(k); chosen.append(j)
    # Sem cotas por fonte ou categoria. Prioridade nacional segue nos critérios
    # de busca e aderencia; nota e data determinam a ordem DENTRO de cada grupo.
    chosen = ordered_jobs(chosen)
    source_counts = {}
    for selected in chosen:
        name = selected["source"]
        source_counts[name] = source_counts.get(name, 0) + 1
    sources.append("Vagas exibidas por fonte: " + ", ".join(
        f"{name}: {count}" for name, count in sorted(source_counts.items())
    ))
    payload=report(chosen,sources)
    html_payload=render_html(chosen,sources,preview=preview,include_seen=include_seen)
    interactive_payload=render_html(chosen,sources,preview=preview,include_seen=include_seen,interactive=True)
    print("Fontes:",sources,"Selecionadas:",len(chosen))
    if preview:
        mode = "DEMONSTRAÇÃO (inclui vagas já apresentadas)" if include_seen else "PRÉVIA (somente vagas ainda não apresentadas)"
        text = (f"{mode} — NÃO ENVIADO POR E-MAIL, NÃO REGISTRADO NO HISTÓRICO.\n"
                "Resultado gerado agora; NÃO é reprodução do e-mail de uma execução anterior.\n\n" + payload)
        output = ROOT / "previa_radar.txt"
        output.write_text(text, encoding="utf-8")
        (ROOT / "previa_radar.html").write_text(html_payload,encoding="utf-8")
        (ROOT / "radar_interativo.html").write_text(interactive_payload,encoding="utf-8")
        print(f"Prévia salva em {output}; sem SMTP e sem alterar vistos.json")
        return
    (ROOT / "radar_interativo.html").write_text(interactive_payload,encoding="utf-8")
    email(payload,html_payload)
    # Publicar a MESMA seleção enviada por e-mail; a execução de prévia nunca altera a página.
    PUBLIC_RADAR_HTML.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_RADAR_HTML.write_text(interactive_payload, encoding="utf-8")
    state["seen"]=sorted(set(state.get("seen",[])) | {fingerprint(j) for j in chosen})
    state["last_email_date"]=today
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Envio SMTP confirmado; histórico atualizado.")

if __name__=="__main__":
    main()
