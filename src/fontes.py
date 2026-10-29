"""
Rodapé de fontes das respostas do chat ("de onde veio isso?").

O pipeline já rastreia `sources` por resposta, mas em rótulos internos
("Knowledge Graph", "Documento - termo_7", "FATOS DO GRAFO ...").
Este módulo traduz esses rótulos para a FONTE OFICIAL de onde o dado veio,
com link quando ele é conhecido e verificado:

  - fatos curriculares do KG (pré-requisito, termo, ementa, coordenação) →
    matriz curricular do(s) curso(s) da UC no SIIU (sistema oficial da Prograd);
  - docentes → página do corpo docente do ICT;
  - oferta/sala/horário → agenda de salas do campus;
  - regulamentos/manuais → o documento oficial (PDF ou página);
  - comunicados → o email (remetente e data), sem link;
  - dados que o aluno digitou → marcados como tal.

Sem link conhecido, a fonte aparece só pelo nome: nunca se inventa URL.
Todas as URLs abaixo foram checadas (HTTP 200) em 28/10/2026.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAX_FONTES = 4

_URL_SIIU = {}  # sigla -> URL da matriz ativa no SIIU (de requisitos_seed.json)
try:
    for _c in json.load(open(Path(__file__).parent / "requisitos_seed.json", encoding="utf-8")):
        if _c.get("fonte") and (_c["sigla"] not in _URL_SIIU or _c.get("turno") == "integral"):
            _URL_SIIU[_c["sigla"]] = _c["fonte"]
except Exception:
    pass

_SITE_CURSO = {
    "BCT": "https://campus.unifesp.br/sjc/graduacao/cursos/bacharelado-interdisciplinar-em-ciencia-e-tecnologia",
    "BCC": "https://campus.unifesp.br/sjc/graduacao/cursos/bacharelado-em-ciencia-da-computacao",
    "BMC": "https://campus.unifesp.br/sjc/graduacao/cursos/bacharelado-em-matematica-computacional",
    "BBT": "https://campus.unifesp.br/sjc/graduacao/cursos/bacharelado-em-biotecnologia",
    "EB": "https://campus.unifesp.br/sjc/graduacao/cursos/engenharia-biomedica",
    "EM": "https://campus.unifesp.br/sjc/graduacao/cursos/engenharia-de-materiais",
    "EC": "https://ecomp.unifesp.br/in%C3%ADcio",
}

URL_AGENDA = "https://agendamentos.unifesp.br/sjc/Web/view-schedule.php"
URL_DOCENTES = "https://unifesp.br/campus/sjc/corpodocente"
URL_DAE = "https://dae-sjc.unifesp.br/"
URL_EC_REGULAMENTOS = "https://ecomp.unifesp.br/o-curso/regulamentos"
URL_RES_246 = "https://unifesp.br/reitoria/prograd/images/docs/2024/Resolucao_2462023_ProGrad.pdf"
URL_REMAT = "https://remat.unifesp.br/app/includes/Manual%20de%20Rematricula%20para%20os%20alunos.pdf"

# Documentos institucionais: (padrão no rótulo normalizado, nome exibido, url|None)
_DOCUMENTOS: List[Tuple[str, str, Optional[str]]] = [
    (r"246|regulamento dos cursos de graduacao",
     "Regulamento dos Cursos de Graduação da Unifesp (Resolução CONSU 246/2023)", URL_RES_246),
    (r"remat|rematricula", "Manual do REMAT (ProGrad)", URL_REMAT),
    (r"manual.*(dae|atividades complementares)|checklist",
     "Manual de Atividades Complementares do BCT (DAE, 2025)", URL_DAE),
    (r"quadro de ucs", "Quadro de UCs do BCT (DAE)", URL_DAE),
    (r"(\bac\b|atividades complementares).*\bbct\b|\bbct\b.*(\bac\b|atividades complementares)",
     "Regulamento de Atividades Complementares do BCT (2023)", URL_DAE),
    (r"(\bac\b|aacc|regulamento).*\bec\b|ecomp|engenharia de computacao",
     "Regulamentos da Engenharia de Computação", URL_EC_REGULAMENTOS),
    (r"(\bac\b|aacc).*\bbbt\b", "Regulamento de AC do BBT (Anexo F do PPC 2023)", None),
    (r"(\bac\b|aacc).*\beb\b", "Regulamento de AACC da Engenharia Biomédica", None),
    (r"(\bac\b|aacc).*\bem\b", "Regulamento de AACC da Engenharia de Materiais", None),
    (r"(\bac\b|aacc).*\bbmc\b", "Regulamento de AACC do BMC", None),
    (r"regimento interno da prograd|matricula em unidades curriculares",
     "Regimento Interno da Prograd: matrícula em UCs (2014)", None),
    (r"regimento interno", "Regimento Interno do ICT/SJC (2022)", None),
    (r"projeto pedagogico|\bppc\b", "Projeto Pedagógico do Curso (PPC)", None),
    (r"criterios.*integralizacao|matrizes curriculares oficiais",
     "Matrizes curriculares oficiais (SIIU/Prograd)", None),
]

# Intents do KG cuja informação vem do cadastro de docentes.
_INTENTS_DOCENTE = {
    "docente_areas", "docente_info", "docente_disciplines", "docentes_by_area",
    "docente_leciona_disciplina", "disciplina_docentes", "discipline_docentes",
    "docente_contato", "contatos_docentes",
}
_SESSAO = "Informações que você deu nesta conversa"

_SIGLA_RE = re.compile(r"\b(BCT|BCC|BMC|BBT)\b", re.I)
_SIGLA_MAIUSC_RE = re.compile(r"\b(EB|EM|EC)\b")  # "em" é preposição: só maiúsculo
_NOMES_CURSO = [
    ("ciencia da computacao", "BCC"), ("matematica computacional", "BMC"),
    ("biotecnologia", "BBT"), ("engenharia biomedica", "EB"),
    ("engenharia de materiais", "EM"), ("engenharia de computacao", "EC"),
    ("ciencia e tecnologia", "BCT"),
]
_URL_RE = re.compile(r"https?://[^\s)\]>\"'*]+")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _cursos_no_texto(texto: str) -> List[str]:
    achados = [m.upper() for m in _SIGLA_RE.findall(texto or "")]
    achados += _SIGLA_MAIUSC_RE.findall(texto or "")
    t = _norm(texto)
    achados += [sig for nome, sig in _NOMES_CURSO if nome in t]
    return list(dict.fromkeys(achados))


def _cursos_da_disciplina(kg, termo: str) -> List[str]:
    """Cursos ligados à UC no grafo (ex.: Compiladores → BCC, EC)."""
    if kg is None or not termo:
        return []
    try:
        node = kg._find_node(termo, "disciplina")
        if not node:
            return []
        g = kg.graph
        viz = set(g.predecessors(node)) | set(g.successors(node))
        sig = [g.nodes[v].get("sigla") for v in viz if g.nodes[v].get("tipo") == "curso"]
        return sorted(s for s in sig if s)
    except Exception:
        return []


def _nome_uc(kg, termo: str) -> str:
    """Nome oficial da UC no grafo (ex.: 'compiladores' → 'Compiladores')."""
    try:
        node = kg._find_node(termo, "disciplina") if kg is not None and termo else None
        return kg.graph.nodes[node].get("nome", "") if node else ""
    except Exception:
        return ""


def _fonte_curricular(cursos: List[str]) -> List[Dict]:
    """Fatos curriculares do KG → matriz do(s) curso(s) no SIIU."""
    out = [{"nome": f"Matriz curricular do {s} (SIIU/Unifesp)", "url": _URL_SIIU[s]}
           for s in cursos if s in _URL_SIIU]
    return out or [{"nome": "Matrizes curriculares e fichas das UCs do ICT (SIIU/Unifesp)",
                    "url": None}]


def _rotulo_url(url: str) -> str:
    """Nome legível para uma página do site a partir da URL."""
    caminho = url.split("://", 1)[-1].split("#")[0].rstrip("/")
    partes = caminho.split("/")
    dominio = partes[0]
    ultimo = partes[-1] if len(partes) > 1 else ""
    if "noticias" in partes and ultimo and ultimo != "noticias":
        return "Notícia do campus: " + ultimo.replace("-", " ")[:70]
    if "cursos" in partes and ultimo:
        secao = url.split("#rlta-", 1)[1].replace("-", " ") if "#rlta-" in url else ""
        return "Site do campus: " + ultimo.replace("-", " ") + (f" ({secao})" if secao else "")
    if dominio.startswith("ecomp."):
        return "Site da Engenharia de Computação"
    if dominio.startswith("dae-sjc."):
        return "Site da DAE-SJC"
    return "Site da Unifesp: " + (ultimo.replace("-", " ") or dominio)


def _links_de_contexto(contexto: str) -> Dict[str, str]:
    """[Título]\\nLink: url  →  {titulo: url} (seções do site no contexto)."""
    return {t.strip(): u for t, u in
            re.findall(r"^\[([^\]]+)\]\s*\nLink:\s*(\S+)", contexto or "", re.M)}


def resolver_fontes(result: Dict, pergunta: str = "", kg=None) -> List[Dict]:
    """
    Lista [{nome, url|None}] das fontes de uma resposta do pipeline, já
    traduzidas para a origem oficial, sem duplicatas e no máximo MAX_FONTES.
    """
    brutas = [str(s) for s in (result.get("sources") or []) if s]
    resposta = result.get("response") or ""
    intent = result.get("intent") or ""
    termo = result.get("term") or ""
    links_ctx = _links_de_contexto(result.get("context") or "")
    citadas = set(u.rstrip(".,;") for u in _URL_RE.findall(resposta))

    fontes: List[Dict] = []
    usa_kg = False

    def add(nome: str, url: Optional[str]):
        fontes.append({"nome": nome, "url": url})

    urls_brutas = [s for s in brutas if s.startswith("http")]
    # Páginas do site: as que a resposta cita; se nenhuma é citada, só as
    # 2 primeiras quando o site é a fonte principal (agentes web/notícias).
    urls_ok = [u for u in urls_brutas if u in citadas or u.split("#")[0] in
               {c.split("#")[0] for c in citadas}]
    if not urls_ok and result.get("active_agent") in ("web_sjc", "noticias"):
        urls_ok = urls_brutas[:2]
    for u in urls_ok:
        add(_rotulo_url(u), u)

    for s in brutas:
        if s.startswith("http"):
            continue
        n = _norm(s)
        if s in links_ctx:  # seção do site no contexto: só se a resposta a citou
            if links_ctx[s] in citadas:
                add("Site do campus: " + s, links_ctx[s])
            continue
        if n.startswith("comunicado:"):
            add("Email institucional · " + s.split(":", 1)[1].strip(), None)
        elif "agenda de salas" in n:
            add("Agenda de salas do campus SJC (oferta do semestre)", URL_AGENDA)
            if "knowledge graph" in n:
                usa_kg = True
        elif "sessao" in n or "historico academico" in n:
            add(_SESSAO, None)
        elif "paginas do site" in n:
            continue  # marcador de bloco; as páginas em si vêm via links_ctx
        elif any(k in n for k in ("knowledge graph", "fatos", "kgc", "grafo",
                                  "disciplina:", "continuacao", "documento -",
                                  "docentes citados")):
            usa_kg = True
            if "docente" in n:
                add("Corpo docente do ICT (Unifesp)", URL_DOCENTES)
        else:
            doc = next(((nome, url) for pad, nome, url in _DOCUMENTOS
                        if re.search(pad, n)), None)
            if doc and doc[0].startswith("Matrizes curriculares oficiais"):
                usa_kg = True
            elif doc:
                add(*doc)
            else:
                add(re.sub(r"\s+-\s+(conteudo|resumo|secao.*)$", "", s), None)

    if usa_kg:
        if intent in _INTENTS_DOCENTE or result.get("active_agent") == "docentes":
            add("Corpo docente do ICT (Unifesp)", URL_DOCENTES)
            cursos = _cursos_da_disciplina(kg, termo)
            if cursos:
                fontes.extend(_fonte_curricular(cursos))
        else:
            cursos = (_cursos_no_texto(termo) or _cursos_da_disciplina(kg, termo)
                      or _cursos_no_texto(pergunta))
            if not cursos and kg is not None:
                for d in (result.get("graph_data") or {}).get("nodes", [])[:1]:
                    cursos = _cursos_da_disciplina(kg, d.get("nome") or d.get("id", ""))
            if intent == "coordenador_curso":
                # coordenação é publicada na página do curso, não no SIIU
                fontes.extend({"nome": f"Página do {c} no site do campus", "url": _SITE_CURSO[c]}
                              for c in cursos if c in _SITE_CURSO)
            else:
                if "ementa" in intent:
                    # ementa vem da ficha da UC (PPC); o SIIU não publica ementa
                    uc = _nome_uc(kg, termo)
                    fontes.append({"nome": f"Ficha da UC{' ' + uc if uc else ''} "
                                           "(ementa do Projeto Pedagógico)", "url": None})
                fontes.extend(_fonte_curricular(cursos))

    vistos, unicas = set(), []
    for f in fontes:
        chave = (f["nome"], (f["url"] or "").split("#")[0])
        if chave in vistos:
            continue
        vistos.add(chave)
        unicas.append(f)
    return unicas[:MAX_FONTES]


def formatar_rodape(fontes: List[Dict]) -> str:
    """Rodapé markdown: '**Fontes:**' + um item por fonte, link quando há."""
    if not fontes:
        return ""
    itens = [f"- [{f['nome']}]({f['url']})" if f.get("url") else f"- {f['nome']}"
             for f in fontes]
    return "\n\n---\n**Fontes:**\n" + "\n".join(itens)
