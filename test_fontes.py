"""Testes do rodapé de fontes (src/fontes.py): rótulos internos → origem oficial."""
from src.fontes import resolver_fontes, formatar_rodape, URL_AGENDA, URL_DOCENTES, URL_RES_246

ok = falhas = 0


def check(nome, cond):
    global ok, falhas
    if cond:
        ok += 1
    else:
        falhas += 1
        print("FALHOU:", nome)


def urls(fs):
    return [f["url"] for f in fs]


def nomes(fs):
    return " | ".join(f["nome"] for f in fs)


# KG genérico + sigla no termo → matriz do curso no SIIU
fs = resolver_fontes({"sources": ["Knowledge Graph"], "intent": "disciplinas_termo",
                      "term": "3º termo do bcc", "response": "..."})
check("kg → SIIU BCC", len(fs) == 1 and "BCC" in fs[0]["nome"] and "siiu" in fs[0]["url"])

# KG sem curso identificável → nome sem link (nunca URL inventada)
fs = resolver_fontes({"sources": ["Knowledge Graph"], "intent": "prerequisite_chain",
                      "term": "", "response": "..."})
check("kg sem curso → sem url", fs and fs[0]["url"] is None)

# docentes
fs = resolver_fontes({"sources": ["Knowledge Graph"], "intent": "docente_info",
                      "term": "", "response": "..."})
check("docente → corpo docente", URL_DOCENTES in urls(fs))

# agenda
fs = resolver_fontes({"sources": ["Agenda de salas do campus SJC (oferta do semestre)"],
                      "intent": "oferta_agenda", "response": "..."})
check("agenda", urls(fs) == [URL_AGENDA])

# regulamento com PDF + seção de vector store
fs = resolver_fontes({"sources": [
    "Regulamento dos Cursos de Graduação da Unifesp - Resolução CONSU nº 246/2023 - conteudo",
    "PAGINAS DO SITE DO CAMPUS - complemento; cite o link ao usar"], "response": "..."})
check("resolução 246 → PDF", urls(fs) == [URL_RES_246])

# AC do BCT não confunde 'ac' dentro de palavra
fs = resolver_fontes({"sources": ["Regulamento de AC do BCT (2023)", "Manual da DAE (2025)"],
                      "response": "..."})
check("AC BCT + manual DAE", len(fs) == 2 and all(f["url"] for f in fs))

# comunicado: email, sem link
fs = resolver_fontes({"sources": ["Comunicado: Feira de estágios (DAE, 22/10/2026)"],
                      "response": "..."})
check("comunicado", fs[0]["url"] is None and fs[0]["nome"].startswith("Email institucional"))

# sessão do aluno
fs = resolver_fontes({"sources": ["Histórico Acadêmico (sessão)"], "response": "..."})
check("sessão", fs[0]["nome"].startswith("Informações que você deu"))

# notícias: só as citadas na resposta; sem citação → 2 primeiras
srcs = [f"https://campus.unifesp.br/sjc/noticias/n{i}" for i in range(9)]
fs = resolver_fontes({"sources": srcs, "active_agent": "noticias",
                      "response": "veja https://campus.unifesp.br/sjc/noticias/n5"})
check("notícia citada", urls(fs) == [srcs[5]])
fs = resolver_fontes({"sources": srcs, "active_agent": "noticias", "response": "sem link"})
check("notícias sem citação → 2", urls(fs) == srcs[:2])

# seção do site no contexto: só entra se a resposta citou o link
ctx = "[TCC da EM]\nLink: https://campus.unifesp.br/sjc/x#rlta-tcc\ntexto"
r = {"sources": ["TCC da EM"], "context": ctx, "response": "nada"}
check("seção não citada fica fora", resolver_fontes(r) == [])
r["response"] = "ver https://campus.unifesp.br/sjc/x#rlta-tcc"
check("seção citada entra", urls(resolver_fontes(r)) == ["https://campus.unifesp.br/sjc/x#rlta-tcc"])

# limite e deduplicação
fs = resolver_fontes({"sources": ["Knowledge Graph", "FATOS DO GRAFO - x", "KGC - y",
                                  "Disciplina: Compiladores - ementa"],
                      "term": "BCC e EC", "response": "..."})
check("dedup KG", len(fs) == 2)

# coordenação → página do curso; ementa → ficha da UC (sem link) + matriz
fs = resolver_fontes({"sources": ["Knowledge Graph"], "intent": "coordenador_curso",
                      "term": "BCC", "response": "..."})
check("coordenação → site do curso", len(fs) == 1 and "campus.unifesp.br" in fs[0]["url"])
fs = resolver_fontes({"sources": ["Disciplina: Compiladores - ementa"], "active_agent": "disciplinas",
                      "intent": "ementa_disciplina", "term": "compiladores BCC", "response": "..."})
check("ementa → ficha + SIIU", fs[0]["url"] is None and "Ficha da UC" in fs[0]["nome"]
      and "siiu" in (fs[1]["url"] or ""))

# rodapé
rod = formatar_rodape([{"nome": "A", "url": "https://a"}, {"nome": "B", "url": None}])
check("rodapé md", "**Fontes:**" in rod and "- [A](https://a)" in rod and "- B" in rod)
check("rodapé vazio", formatar_rodape([]) == "")

print(f"\n{ok}/{ok + falhas} testes de fontes passaram")
raise SystemExit(1 if falhas else 0)
