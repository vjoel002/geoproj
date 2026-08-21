import asyncio
import uuid

from vanna.integrations.openai import OpenAILlmService
from vanna.tools.agent_memory import SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool, SaveTextMemoryTool
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna import Agent
from vanna.tools import VisualizeDataTool, RunSqlTool
from vanna.integrations.postgres import PostgresRunner
from vanna.servers.fastapi import VannaFastAPIServer
from vanna.core.tool import ToolContext
from vanna.core.user import RequestContext, User

# ── FastAPI / GeoJSON extras ──────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras
import json

# ─────────────────────────────────────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────────────────────────────────────
llm = OpenAILlmService(
    api_key="REMOVED_OPENAI_KEY",
    model="gpt-4",
)

# ─────────────────────────────────────────────────────────────────────────────
# Banco de dados (Vanna tool)
# ─────────────────────────────────────────────────────────────────────────────
DB_CONFIG = dict(
    host="localhost",
    port=5432,
    database="IBGEData",
    user="postgres_local",
    password="postgres",
)

db_tool = RunSqlTool(sql_runner=PostgresRunner(**DB_CONFIG))

# ─────────────────────────────────────────────────────────────────────────────
# Memória & ferramentas
# ─────────────────────────────────────────────────────────────────────────────
agent_memory = DemoAgentMemory(max_items=1000)

tools = ToolRegistry()
tools.register_local_tool(db_tool,                          access_groups=["admin", "user"])
tools.register_local_tool(SaveQuestionToolArgsTool(),       access_groups=["admin"])
tools.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=["admin", "user"])
tools.register_local_tool(SaveTextMemoryTool(),             access_groups=["admin", "user"])
tools.register_local_tool(VisualizeDataTool(),              access_groups=["admin", "user"])

# ─────────────────────────────────────────────────────────────────────────────
# Autenticação
# ─────────────────────────────────────────────────────────────────────────────
class SimpleUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        email = request_context.get_cookie("vanna_email") or "joelviltus.edu@gmail.com"
        group = "admin" if email == "joelviltus.edu@gmail.com" else "user"
        return User(id=email, email=email, group_memberships=[group])

user_resolver = SimpleUserResolver()

# ─────────────────────────────────────────────────────────────────────────────
# Agente
# ─────────────────────────────────────────────────────────────────────────────
agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=user_resolver,
    agent_memory=agent_memory,
)

# ─────────────────────────────────────────────────────────────────────────────
# Servidor Vanna (FastAPI interno)
# ─────────────────────────────────────────────────────────────────────────────
server = VannaFastAPIServer(agent)
app: FastAPI = server.create_app()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

#===============================================================================================
from fastapi.responses import FileResponse
#import os

#BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/app")
def serve_index():
    return FileResponse(r"C:\Users\joelv\Desktop\temp\PROJET\myproject\AppGeo\templates\geo\index.html")
# ==============================================================================================

# ─────────────────────────────────────────────────────────────────────────────
# Helper: conexão direta ao Postgres
# ─────────────────────────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ─────────────────────────────────────────────────────────────────────────────
# Cliente OpenAI direto (dependência já instalada pelo Vanna)
# ─────────────────────────────────────────────────────────────────────────────
from openai import AsyncOpenAI

_openai_client = AsyncOpenAI(
    api_key="REMOVED_OPENAI_KEY",
)
OPENAI_MODEL = "gpt-4o-mini"   # rápido e barato; troque por "gpt-4o" se quiser mais precisão

async def _chat(system: str, user: str) -> str:
    """Chama o OpenAI diretamente e retorna o texto da resposta."""
    resp = await _openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0,
        max_tokens=512,
    )
    return resp.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Treinamento: exemplos pergunta→SQL que guiam o LLM via few-shot
# Edite a lista training_examples abaixo para adicionar/corrigir exemplos.
# ─────────────────────────────────────────────────────────────────────────────
import difflib

training_examples: list[dict] = []  # preenchido em init_training() mais abaixo

SCHEMA_HINT_BASE = """Você é um especialista em SQL/PostGIS.
Você tem acesso a DUAS tabelas no banco IBGEData:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABELA 1: br_municipios_2023  (municípios)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Colunas:
  gid         SERIAL PRIMARY KEY
  cd_mun      VARCHAR  -- código IBGE do município (7 dígitos)
  nm_mun      VARCHAR  -- nome do município
  cd_rgi      VARCHAR  -- código da Região Geográfica Imediata
  nm_rgi      VARCHAR  -- nome da Região Geográfica Imediata (ex: 'Campo Grande', 'Campinas')
  cd_rgint    VARCHAR  -- código da Região Geográfica Intermediária
  nm_rgint    VARCHAR  -- nome da Região Geográfica Intermediária (ex: 'São Paulo', 'Campinas')
  cd_uf       VARCHAR  -- código numérico do estado (ex: '35' = São Paulo, '50' = Mato Grosso do Sul)
  nm_uf       VARCHAR  -- nome completo do estado (ex: 'São Paulo', 'Mato Grosso do Sul')
  cd_regiao   VARCHAR  -- código da região (1=Norte, 2=Nordeste, 3=Sudeste, 4=Sul, 5=Centro-oeste)
  nm_regiao   VARCHAR  -- nome da região (ex: 'Sudeste', 'Norte', 'Centro-oeste')
  cd_concurb  VARCHAR  -- código da concentração urbana (NULL se não pertence)
  nm_concurb  VARCHAR  -- nome da concentração urbana / área metropolitana (ex: 'São Paulo/SP', 'Campinas/SP')
  area_km2    DOUBLE   -- área em km²
  geom        GEOMETRY -- polígono WGS84

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABELA 2: br_uf_2023  (estados / unidades da federação)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Colunas:
  gid         SERIAL PRIMARY KEY
  cd_uf       VARCHAR  -- código numérico do estado (ex: '35' = SP, '50' = MS)
  nm_uf       VARCHAR  -- nome completo do estado (ex: 'São Paulo', 'Mato Grosso do Sul')
  sigla_uf    VARCHAR  -- sigla do estado (ex: 'SP', 'MS', 'RJ', 'MG')
  cd_regiao   VARCHAR  -- código da região (1=Norte, 2=Nordeste, 3=Sudeste, 4=Sul, 5=Centro-oeste)
  nm_regiao   VARCHAR  -- nome da região (ex: 'Sudeste', 'Norte', 'Centro-oeste')
  area_km2    DOUBLE   -- área total do estado em km²
  geom        GEOMETRY -- polígono do estado WGS84

Relação entre tabelas:
  br_municipios_2023.cd_uf = br_uf_2023.cd_uf  (JOIN por código do estado)
  br_municipios_2023.nm_uf = br_uf_2023.nm_uf  (JOIN alternativo por nome)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Valores reais de nm_uf (use EXATAMENTE assim):
  'Acre', 'Alagoas', 'Amapá', 'Amazonas', 'Bahia', 'Ceará', 'Distrito Federal',
  'Espírito Santo', 'Goiás', 'Maranhão', 'Mato Grosso', 'Mato Grosso do Sul',
  'Minas Gerais', 'Pará', 'Paraíba', 'Paraná', 'Pernambuco', 'Piauí',
  'Rio de Janeiro', 'Rio Grande do Norte', 'Rio Grande do Sul', 'Rondônia',
  'Roraima', 'Santa Catarina', 'São Paulo', 'Sergipe', 'Tocantins'

Valores reais de nm_regiao: 'Norte', 'Nordeste', 'Sudeste', 'Sul', 'Centro-oeste'

Valores reais de sigla_uf: 'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS',
  'MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regras OBRIGATÓRIAS:
- Responda SOMENTE com SQL válido para PostgreSQL, sem explicação.
- Não use blocos markdown (sem ```).
- Não inclua ponto-e-vírgula no final.
- Use br_uf_2023 para perguntas sobre estados (polígono, área, sigla, listagem de UFs).
- Use br_municipios_2023 para perguntas sobre municípios.
- Para perguntas que envolvam ambos, use JOIN: br_municipios_2023 m JOIN br_uf_2023 u ON m.cd_uf = u.cd_uf
- Para filtros de estado use nm_uf com o nome EXATO da lista acima, ou sigla_uf com a sigla.
- Para região metropolitana ou área urbana, use nm_concurb ILIKE '%termo%'.
- Para região geográfica imediata, use nm_rgi ILIKE '%termo%'.
- Para região geográfica intermediária, use nm_rgint ILIKE '%termo%'.
- Para região do Brasil (Norte/Sul etc), use nm_regiao = 'Nome'.
- Para buscas por nome de município, use nm_mun ILIKE '%termo%'.
- Para consultas em br_municipios_2023, SEMPRE inclua cd_mun e nm_mun no SELECT (permitem destaque no mapa).
- Para consultas em br_uf_2023, SEMPRE inclua cd_uf, nm_uf e sigla_uf no SELECT."""


def _build_system_prompt(question: str) -> tuple[str, str | None]:
    """
    Monta o system prompt com few-shot examples.
    Retorna (system_prompt, sql_exato) — sql_exato preenchido só em match exato.
    """
    # 1. Match exato (case-insensitive)
    q_lower = question.strip().lower()
    for ex in training_examples:
        if ex["question"].strip().lower() == q_lower:
            return SCHEMA_HINT_BASE, ex["sql"].strip().rstrip(";")

    # 2. Match fuzzy — os 5 mais similares viram few-shot
    questions = [e["question"] for e in training_examples]
    close = difflib.get_close_matches(question, questions, n=5, cutoff=0.35)
    pool  = [e for e in training_examples if e["question"] in close]
    # Completa com os primeiros da lista até 8 exemplos
    seen = {e["question"] for e in pool}
    for e in training_examples:
        if len(pool) >= 8:
            break
        if e["question"] not in seen:
            pool.append(e)
            seen.add(e["question"])

    if pool:
        few_shot = "\n\nExemplos (use como referência de estilo e tabela):\n"
        for ex in pool:
            few_shot += f'\nPergunta: {ex["question"]}\nSQL: {ex["sql"]}\n'
        return SCHEMA_HINT_BASE + few_shot, None

    return SCHEMA_HINT_BASE, None


async def question_to_sql(question: str) -> str:
    system, exact_sql = _build_system_prompt(question)

    # Match exato no treinamento → usa direto, sem gastar tokens
    if exact_sql:
        sql = exact_sql.rstrip(";") + ";"
        print(f"[train] match exato: {question!r}")
        return sql

    sql = await _chat(system, f"Pergunta: {question}")
    sql = sql.replace("```sql", "").replace("```", "").strip().rstrip(";") + ";"
    return sql


# ─────────────────────────────────────────────────────────────────────────────
# Helper: interpreta resultado e gera resposta textual
# ─────────────────────────────────────────────────────────────────────────────
async def rows_to_text(question: str, sql: str, rows: list[dict]) -> str:
    system = (
        "Você é um assistente de dados geográficos. "
        "Recebe uma pergunta, o SQL executado e os resultados, "
        "e redige uma resposta amigável em português brasileiro. "
        "Seja conciso (máx 4 frases). Não liste todos os dados brutos — "
        "resuma os principais achados. Se for contagem, mencione o número. "
        "Se for ranking, destaque os primeiros colocados."
    )
    user = (
        f"Pergunta: {question}\n"
        f"SQL executado:\n{sql}\n\n"
        f"Resultados (primeiros {min(len(rows),50)}):\n"
        f"{json.dumps(rows[:50], ensure_ascii=False, default=str)}"
    )
    return await _chat(system, user)


# ─────────────────────────────────────────────────────────────────────────────
# POST /ask  — pergunta em linguagem natural
#
# Body JSON: { "question": "Quais os 5 maiores municípios do MS?" }
#
# Resposta JSON:
# {
#   "question": "...",
#   "sql":      "SELECT ...",
#   "answer":   "Texto amigável gerado pelo LLM",
#   "chart": {
#       "labels": ["Município A", ...],
#       "values": [12345.6, ...],
#       "x_label": "Nome",
#       "y_label": "Área (km²)"
#   },
#   "rows": [{ ... }, ...],    -- dados brutos (máx 200)
#   "total_rows": 5
# }
# ─────────────────────────────────────────────────────────────────────────────
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
    sql: str | None = None  # se fornecido, usa diretamente sem chamar o LLM

@app.post("/ask")
async def ask(body: AskRequest):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Campo 'question' não pode ser vazio.")

    # 1. Gera SQL
    try:
        sql = await question_to_sql(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar SQL: {e}")

    # 2. Executa SQL
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchmany(200)]
            # Remove coluna geometry (pode ser muito grande)
            for r in rows:
                r.pop("geom", None)
                r.pop("geometry", None)
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar SQL: {e}")

    # 3. Gera texto amigável
    try:
        answer = await rows_to_text(question, sql, rows)
    except Exception as e:
        answer = f"Consulta executada com sucesso. {len(rows)} registro(s) retornado(s)."

    # 4. Monta dados para gráfico (tenta detectar colunas automaticamente)
    chart = None
    if rows:
        cols = list(rows[0].keys())
        # Heurística: primeira coluna de texto = labels, primeira numérica = valores
        label_col = next((c for c in cols if isinstance(rows[0][c], str)), None)
        value_col = next(
            (c for c in cols if isinstance(rows[0][c], (int, float)) and c != "gid"),
            None
        )
        if label_col and value_col and len(rows) > 1:
            chart = {
                "labels":  [str(r[label_col]) for r in rows[:30]],
                "values":  [float(r[value_col]) if r[value_col] is not None else 0 for r in rows[:30]],
                "x_label": label_col,
                "y_label": value_col,
            }
        elif value_col and len(rows) == 1:
            # Resultado único escalar — não exige gráfico
            chart = None

    return {
        "question":   question,
        "sql":        sql,
        "answer":     answer,
        "chart":      chart,
        "rows":       rows,
        "total_rows": len(rows),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /ask/geojson  — recebe o SQL gerado pelo /ask e retorna GeoJSON.
#
# Detecta automaticamente se a consulta é sobre municípios (br_municipios_2023)
# ou estados (br_uf_2023) e faz o join correto para buscar as geometrias.
# Body: { "question": "...", "sql": "SELECT ..." }
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/ask/geojson")
async def ask_geojson(body: AskRequest, tolerance: float = 0.005):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Campo 'question' nao pode ser vazio.")

    if body.sql:
        sql = body.sql
    else:
        try:
            sql = await question_to_sql(question)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao gerar SQL: {e}")

    # Remove ponto-e-virgula final para usar como subquery
    sql_clean = sql.strip().rstrip(";")

    # Detecta colunas retornadas para decidir qual tabela usar no join geométrico
    col_names = []
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM ({sql_clean}) _probe LIMIT 0")
            col_names = [d.name for d in cur.description] if cur.description else []
        conn.close()
    except Exception:
        col_names = []

    has_cd_mun = "cd_mun" in col_names
    has_cd_uf  = "cd_uf"  in col_names
    has_nm_uf  = "nm_uf"  in col_names
    has_sigla  = "sigla_uf" in col_names

    # ── Decide se a consulta é sobre estados ou municípios ──────────────────
    # Heurística: tem cd_uf/sigla_uf mas NÃO tem cd_mun → consulta de estados
    is_uf_query = (has_cd_uf or has_sigla) and not has_cd_mun

    if is_uf_query:
        # ── JOIN em br_uf_2023 ───────────────────────────────────────────────
        if has_cd_uf:
            join_cond = "g.cd_uf = sub.cd_uf::text"
        elif has_sigla:
            join_cond = "g.sigla_uf = sub.sigla_uf::text"
        else:
            join_cond = "g.nm_uf = sub.nm_uf"

        geo_sql = """
            SELECT DISTINCT ON (g.cd_uf)
                   g.gid, g.cd_uf, g.nm_uf, g.sigla_uf, g.nm_regiao, g.area_km2,
                   ST_AsGeoJSON(
                       CASE WHEN {tol} > 0
                            THEN ST_Simplify(g.geom, {tol}, true)
                            ELSE g.geom END
                   )::json AS geometry
            FROM br_uf_2023 g
            INNER JOIN (
                {sub}
            ) sub ON {join}
            ORDER BY g.cd_uf
        """.format(tol=tolerance, sub=sql_clean, join=join_cond)

        try:
            conn = get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(geo_sql)
                geo_rows = cur.fetchall()
            conn.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao buscar geometrias de estados: {e}")

        features = [
            {
                "type": "Feature",
                "geometry": row["geometry"],
                "properties": {
                    "gid":       row["gid"],
                    "cd_uf":     row["cd_uf"],
                    "nm_uf":     row["nm_uf"] or "—",
                    "sigla_uf":  row["sigla_uf"] or "—",
                    "nm_regiao": row["nm_regiao"] or "—",
                    "area_km2":  float(row["area_km2"]) if row["area_km2"] else None,
                },
            }
            for row in geo_rows
        ]

    else:
        # ── JOIN em br_municipios_2023 (comportamento original) ──────────────
        if has_cd_mun:
            join_cond = "g.cd_mun = sub.cd_mun::text"
        else:
            join_cond = "g.nm_mun = sub.nm_mun AND g.nm_uf = sub.nm_uf"

        geo_sql = """
            SELECT DISTINCT ON (g.cd_mun)
                   g.gid, g.cd_mun, g.nm_mun, g.nm_uf, g.area_km2,
                   ST_AsGeoJSON(
                       CASE WHEN {tol} > 0
                            THEN ST_Simplify(g.geom, {tol}, true)
                            ELSE g.geom END
                   )::json AS geometry
            FROM br_municipios_2023 g
            INNER JOIN (
                {sub}
            ) sub ON {join}
            ORDER BY g.cd_mun
        """.format(tol=tolerance, sub=sql_clean, join=join_cond)

        try:
            conn = get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(geo_sql)
                geo_rows = cur.fetchall()
            conn.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao buscar geometrias de municípios: {e}")

        features = [
            {
                "type": "Feature",
                "geometry": row["geometry"],
                "properties": {
                    "gid":      row["gid"],
                    "cd_mun":   row["cd_mun"],
                    "nm_mun":   row["nm_mun"],
                    "nm_uf":    row["nm_uf"] or "—",
                    "area_km2": float(row["area_km2"]) if row["area_km2"] else None,
                },
            }
            for row in geo_rows
        ]

    return JSONResponse(
        content={"type": "FeatureCollection", "features": features},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints GeoJSON originais (mantidos para compatibilidade)
# ─────────────────────────────────────────────────────────────────────────────
from fastapi.responses import StreamingResponse
import json as _json

CURSOR_BATCH = 200

def _row_to_feature(row) -> str:
    props = {
        "gid":      row["gid"],
        "cd_mun":   row["cd_mun"],
        "nm_mun":   row["nm_mun"],
        "nm_uf":    row["nm_uf"] or "—",
        "area_km2": float(row["area_km2"]) if row["area_km2"] else None,
    }
    feature = {
        "type":       "Feature",
        "geometry":   row["geometry"],
        "properties": props,
    }
    return _json.dumps(feature, ensure_ascii=False)


@app.get("/geojson/municipios/stream")
def stream_municipios_geojson(tolerance: float = 0.001):
    sql = """
        SELECT
            gid, cd_mun, nm_mun, nm_uf, area_km2,
            ST_AsGeoJSON(
                CASE WHEN %(tol)s > 0
                     THEN ST_Simplify(geom, %(tol)s, true)
                     ELSE geom END
            )::json AS geometry
        FROM br_municipios_2023
        ORDER BY nm_mun;
    """

    def generate():
        conn = psycopg2.connect(**DB_CONFIG)
        try:
            with conn.cursor(name="stream_mun", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {"tol": tolerance})
                yield '{"type":"FeatureCollection","features":[\n'
                first = True
                while True:
                    rows = cur.fetchmany(CURSOR_BATCH)
                    if not rows:
                        break
                    for row in rows:
                        prefix = "" if first else ","
                        first = False
                        yield prefix + _row_to_feature(row) + "\n"
            yield "]}\n"
        finally:
            conn.close()

    return StreamingResponse(
        generate(),
        media_type="application/geo+json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/geojson/municipios", response_class=JSONResponse)
def get_municipios_geojson(page: int = 1, page_size: int = 50, tolerance: float = 0.001):
    page_size = min(page_size, 200)
    offset    = (page - 1) * page_size
    sql_count = "SELECT COUNT(*) FROM br_municipios_2023;"
    sql_data  = """
        SELECT gid, cd_mun, nm_mun, nm_uf, area_km2,
               ST_AsGeoJSON(
                   CASE WHEN %(tol)s > 0
                        THEN ST_Simplify(geom, %(tol)s, true)
                        ELSE geom END
               )::json AS geometry
        FROM br_municipios_2023
        ORDER BY nm_mun
        LIMIT %(lim)s OFFSET %(off)s;
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql_count)
            total = cur.fetchone()["count"]
            cur.execute(sql_data, {"tol": tolerance, "lim": page_size, "off": offset})
            rows = cur.fetchall()
    finally:
        conn.close()

    features = [
        {
            "type": "Feature",
            "geometry": row["geometry"],
            "properties": {
                "gid":      row["gid"],
                "cd_mun":   row["cd_mun"],
                "nm_mun":   row["nm_mun"],
                "nm_uf":    row["nm_uf"] or "—",
                "area_km2": float(row["area_km2"]) if row["area_km2"] else None,
            },
        }
        for row in rows
    ]

    return {
        "type":      "FeatureCollection",
        "features":  features,
        "pagination": {
            "page":        page,
            "page_size":   page_size,
            "total":       total,
            "total_pages": -(-total // page_size),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# GeoJSON — Estados (br_uf_2023)
# GET /geojson/estados/stream  — streaming de todos os estados
# GET /geojson/estados          — paginado
# ─────────────────────────────────────────────────────────────────────────────
def _row_to_feature_uf(row) -> str:
    props = {
        "gid":      row["gid"],
        "cd_uf":    row["cd_uf"],
        "nm_uf":    row["nm_uf"] or "—",
        "sigla_uf": row["sigla_uf"] or "—",
        "nm_regiao": row.get("nm_regiao") or "—",
        "area_km2": float(row["area_km2"]) if row["area_km2"] else None,
    }
    feature = {
        "type":       "Feature",
        "geometry":   row["geometry"],
        "properties": props,
    }
    return _json.dumps(feature, ensure_ascii=False)


@app.get("/geojson/estados/stream")
def stream_estados_geojson(tolerance: float = 0.005):
    sql = """
        SELECT
            gid, cd_uf, nm_uf, sigla_uf, nm_regiao, area_km2,
            ST_AsGeoJSON(
                CASE WHEN %(tol)s > 0
                     THEN ST_Simplify(geom, %(tol)s, true)
                     ELSE geom END
            )::json AS geometry
        FROM br_uf_2023
        ORDER BY nm_uf;
    """

    def generate():
        conn = psycopg2.connect(**DB_CONFIG)
        try:
            with conn.cursor(name="stream_uf", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {"tol": tolerance})
                yield '{"type":"FeatureCollection","features":[\n'
                first = True
                while True:
                    rows = cur.fetchmany(CURSOR_BATCH)
                    if not rows:
                        break
                    for row in rows:
                        prefix = "" if first else ","
                        first = False
                        yield prefix + _row_to_feature_uf(row) + "\n"
            yield "]}\n"
        finally:
            conn.close()

    return StreamingResponse(
        generate(),
        media_type="application/geo+json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/geojson/estados", response_class=JSONResponse)
def get_estados_geojson(page: int = 1, page_size: int = 30, tolerance: float = 0.005):
    page_size = min(page_size, 100)
    offset    = (page - 1) * page_size
    sql_count = "SELECT COUNT(*) FROM br_uf_2023;"
    sql_data  = """
        SELECT gid, cd_uf, nm_uf, sigla_uf, nm_regiao, area_km2,
               ST_AsGeoJSON(
                   CASE WHEN %(tol)s > 0
                        THEN ST_Simplify(geom, %(tol)s, true)
                        ELSE geom END
               )::json AS geometry
        FROM br_uf_2023
        ORDER BY nm_uf
        LIMIT %(lim)s OFFSET %(off)s;
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql_count)
            total = cur.fetchone()["count"]
            cur.execute(sql_data, {"tol": tolerance, "lim": page_size, "off": offset})
            rows = cur.fetchall()
    finally:
        conn.close()

    features = [
        {
            "type": "Feature",
            "geometry": row["geometry"],
            "properties": {
                "gid":      row["gid"],
                "cd_uf":    row["cd_uf"],
                "nm_uf":    row["nm_uf"] or "—",
                "sigla_uf": row["sigla_uf"] or "—",
                "nm_regiao": row["nm_regiao"] or "—",
                "area_km2": float(row["area_km2"]) if row["area_km2"] else None,
            },
        }
        for row in rows
    ]

    return {
        "type":      "FeatureCollection",
        "features":  features,
        "pagination": {
            "page":        page,
            "page_size":   page_size,
            "total":       total,
            "total_pages": -(-total // page_size),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Download Shapefile (mantido)
# ─────────────────────────────────────────────────────────────────────────────
import io, zipfile, json as _json2, os
from fastapi.responses import StreamingResponse as _SR
from shapely.geometry import shape, mapping

_proj_data = os.path.join(os.path.dirname(__import__("fiona").__file__), "proj_data")
if os.path.isdir(_proj_data):
    os.environ.setdefault("PROJ_DATA", _proj_data)
    os.environ.setdefault("PROJ_LIB",  _proj_data)

import fiona

WGS84_WKT = (
    'GEOGCS["WGS 84",'
    'DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
    'AUTHORITY["EPSG","4326"]]'
)


import tempfile, glob

# ─────────────────────────────────────────────────────────────────────────────
# Download Shapefile — RESULTADO DA CONSULTA (múltiplos municípios)
# POST /download/shapefile/result
# Body: { "cd_muns": ["5003207", ...], "filename": "resultado" }
# ─────────────────────────────────────────────────────────────────────────────
class ShapefileResultRequest(BaseModel):
    cd_muns:  list[str]
    filename: str = "resultado_consulta"

@app.post("/download/shapefile/result")
def download_shapefile_result(body: ShapefileResultRequest):
    if not body.cd_muns:
        raise HTTPException(status_code=400, detail="Lista cd_muns está vazia.")

    sql_q = """
        SELECT cd_mun, nm_mun, nm_uf, area_km2,
               ST_AsGeoJSON(geom) AS geometry
        FROM br_municipios_2023
        WHERE cd_mun = ANY(%(ids)s)
        ORDER BY nm_mun;
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql_q, {"ids": body.cd_muns})
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="Nenhum município encontrado.")

    first_geom = shape(_json2.loads(rows[0]["geometry"]))
    geom_type  = first_geom.geom_type

    schema = {
        "geometry": geom_type,
        "properties": {"cd_mun": "str", "nm_mun": "str", "nm_uf": "str", "area_km2": "float"},
    }

    nome_arquivo = body.filename.replace(" ", "_")[:60]

    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = os.path.join(tmpdir, f"{nome_arquivo}.shp")
        with fiona.open(shp_path, mode="w", driver="ESRI Shapefile",
                        schema=schema, crs=WGS84_WKT, encoding="utf-8") as dst:
            for row in rows:
                geom = shape(_json2.loads(row["geometry"]))
                if geom_type == "MultiPolygon" and geom.geom_type == "Polygon":
                    from shapely.geometry import MultiPolygon
                    geom = MultiPolygon([geom])
                dst.write({
                    "geometry": mapping(geom),
                    "properties": {
                        "cd_mun":   row["cd_mun"],
                        "nm_mun":   row["nm_mun"],
                        "nm_uf":    row["nm_uf"] or "",
                        "area_km2": float(row["area_km2"]) if row["area_km2"] else 0.0,
                    },
                })

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in glob.glob(os.path.join(tmpdir, f"{nome_arquivo}.*")):
                zf.write(fpath, arcname=os.path.basename(fpath))

    return _SR(
        io.BytesIO(zip_buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{nome_arquivo}.zip"',
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Download Shapefile — MUNICÍPIO ÚNICO (mantido para compatibilidade)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/download/shapefile/{cd_mun}")
def download_shapefile(cd_mun: str):
    sql = """
        SELECT cd_mun, nm_mun, nm_uf, area_km2,
               ST_AsGeoJSON(geom) AS geometry
        FROM br_municipios_2023
        WHERE cd_mun = %(cd)s;
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"cd": cd_mun})
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Município {cd_mun} não encontrado.")

    geom   = shape(_json2.loads(row["geometry"]))
    schema = {
        "geometry": geom.geom_type,
        "properties": {"cd_mun": "str", "nm_mun": "str", "nm_uf": "str", "area_km2": "float"},
    }
    record = {
        "geometry": mapping(geom),
        "properties": {
            "cd_mun":   row["cd_mun"],
            "nm_mun":   row["nm_mun"],
            "nm_uf":    row["nm_uf"] or "",
            "area_km2": float(row["area_km2"]) if row["area_km2"] else 0.0,
        },
    }

    import tempfile, glob
    nome = row["nm_mun"].replace(" ", "_")
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = os.path.join(tmpdir, f"{nome}.shp")
        with fiona.open(shp_path, mode="w", driver="ESRI Shapefile",
                        schema=schema, crs=WGS84_WKT, encoding="utf-8") as dst:
            dst.write(record)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in glob.glob(os.path.join(tmpdir, f"{nome}.*")):
                zf.write(fpath, arcname=os.path.basename(fpath))

    return _SR(
        io.BytesIO(zip_buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}.zip"',
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Treinamento inicial
# Edite esta lista para adicionar/corrigir exemplos.
# IMPORTANTE:
#   - Consultas em br_municipios_2023: inclua cd_mun e nm_mun no SELECT.
#   - Consultas em br_uf_2023: inclua cd_uf, nm_uf e sigla_uf no SELECT.
#   - Isso permite o destaque correto no mapa para ambas as tabelas.
# ─────────────────────────────────────────────────────────────────────────────
TRAINING_FILE = "training_examples.json"

DEFAULT_EXAMPLES = [
    # ── br_municipios_2023 ────────────────────────────────────────────────────
    {"question": "Quantos municípios existem?",
     "sql": "SELECT COUNT(*) AS total FROM br_municipios_2023"},
    {"question": "Quantos municípios existem no Mato Grosso do Sul?",
     "sql": "SELECT COUNT(*) AS total FROM br_municipios_2023 WHERE nm_uf = 'Mato Grosso do Sul'"},
    {"question": "Liste todos os municípios",
     "sql": "SELECT cd_mun, nm_mun, nm_uf FROM br_municipios_2023 ORDER BY nm_mun"},
    {"question": "Qual o maior município por área?",
     "sql": "SELECT cd_mun, nm_mun, nm_uf, area_km2 FROM br_municipios_2023 ORDER BY area_km2 DESC LIMIT 1"},
    {"question": "Quais os 10 maiores municípios do Brasil por área?",
     "sql": "SELECT cd_mun, nm_mun, nm_uf, area_km2 FROM br_municipios_2023 ORDER BY area_km2 DESC LIMIT 10"},
    {"question": "Qual o código IBGE de Campo Grande?",
     "sql": "SELECT cd_mun, nm_mun FROM br_municipios_2023 WHERE nm_mun ILIKE '%Campo Grande%'"},
    {"question": "Quais municípios do Mato Grosso do Sul têm mais de 5000 km²?",
     "sql": "SELECT cd_mun, nm_mun, area_km2 FROM br_municipios_2023 WHERE nm_uf = 'Mato Grosso do Sul' AND area_km2 > 5000 ORDER BY area_km2 DESC"},
    {"question": "Liste os estados e a quantidade de municípios de cada um",
     "sql": "SELECT nm_uf, COUNT(*) AS total FROM br_municipios_2023 GROUP BY nm_uf ORDER BY total DESC"},
    {"question": "Liste os municípios do Mato Grosso do Sul",
     "sql": "SELECT cd_mun, nm_mun, area_km2 FROM br_municipios_2023 WHERE nm_uf = 'Mato Grosso do Sul' ORDER BY nm_mun"},
    {"question": "Liste os municípios da região metropolitana de São Paulo",
     "sql": "SELECT cd_mun, nm_mun, nm_uf, nm_concurb FROM br_municipios_2023 WHERE nm_concurb ILIKE '%São Paulo%' ORDER BY nm_mun"},
    {"question": "Quais municípios pertencem à região metropolitana de Campinas?",
     "sql": "SELECT cd_mun, nm_mun, nm_concurb FROM br_municipios_2023 WHERE nm_concurb ILIKE '%Campinas%' ORDER BY nm_mun"},
    {"question": "Liste os municípios da região Norte do Brasil",
     "sql": "SELECT cd_mun, nm_mun, nm_uf FROM br_municipios_2023 WHERE nm_regiao = 'Norte' ORDER BY nm_uf, nm_mun"},
    {"question": "Liste os municípios da região Sudeste",
     "sql": "SELECT cd_mun, nm_mun, nm_uf FROM br_municipios_2023 WHERE nm_regiao = 'Sudeste' ORDER BY nm_uf, nm_mun"},
    {"question": "Quais municípios fazem parte da região geográfica imediata de Campo Grande?",
     "sql": "SELECT cd_mun, nm_mun, nm_rgi FROM br_municipios_2023 WHERE nm_rgi ILIKE '%Campo Grande%' ORDER BY nm_mun"},
    {"question": "Liste os municípios da região geográfica intermediária de São Paulo",
     "sql": "SELECT cd_mun, nm_mun, nm_rgint FROM br_municipios_2023 WHERE nm_rgint ILIKE '%São Paulo%' ORDER BY nm_mun"},
    {"question": "Quantos municípios existem por região do Brasil?",
     "sql": "SELECT nm_regiao, COUNT(*) AS total FROM br_municipios_2023 GROUP BY nm_regiao ORDER BY total DESC"},

    # ── br_uf_2023 ────────────────────────────────────────────────────────────
    {"question": "Liste todos os estados do Brasil",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, nm_regiao, area_km2 FROM br_uf_2023 ORDER BY nm_uf"},
    {"question": "Quantos estados existem no Brasil?",
     "sql": "SELECT COUNT(*) AS total FROM br_uf_2023"},
    {"question": "Qual a sigla do Mato Grosso do Sul?",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf FROM br_uf_2023 WHERE nm_uf = 'Mato Grosso do Sul'"},
    {"question": "Liste os estados da região Centro-oeste",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, area_km2 FROM br_uf_2023 WHERE nm_regiao = 'Centro-oeste' ORDER BY nm_uf"},
    {"question": "Liste os estados da região Sudeste",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, area_km2 FROM br_uf_2023 WHERE nm_regiao = 'Sudeste' ORDER BY nm_uf"},
    {"question": "Liste os estados da região Norte",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, area_km2 FROM br_uf_2023 WHERE nm_regiao = 'Norte' ORDER BY nm_uf"},
    {"question": "Qual o maior estado por área?",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, area_km2 FROM br_uf_2023 ORDER BY area_km2 DESC LIMIT 1"},
    {"question": "Quais os 5 maiores estados por área?",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, area_km2 FROM br_uf_2023 ORDER BY area_km2 DESC LIMIT 5"},
    {"question": "Qual o menor estado por área?",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, area_km2 FROM br_uf_2023 ORDER BY area_km2 ASC LIMIT 1"},
    {"question": "Qual a área do estado de São Paulo?",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf, area_km2 FROM br_uf_2023 WHERE nm_uf = 'São Paulo'"},
    {"question": "Quantos estados existem por região?",
     "sql": "SELECT nm_regiao, COUNT(*) AS total FROM br_uf_2023 GROUP BY nm_regiao ORDER BY total DESC"},
    {"question": "Qual o código IBGE do estado do Mato Grosso do Sul?",
     "sql": "SELECT cd_uf, nm_uf, sigla_uf FROM br_uf_2023 WHERE nm_uf = 'Mato Grosso do Sul'"},

    # ── JOIN entre as duas tabelas ────────────────────────────────────────────
    {"question": "Quantos municípios tem cada estado e qual a área total do estado?",
     "sql": "SELECT u.cd_uf, u.nm_uf, u.sigla_uf, u.area_km2 AS area_estado_km2, COUNT(m.cd_mun) AS total_municipios FROM br_uf_2023 u LEFT JOIN br_municipios_2023 m ON u.cd_uf = m.cd_uf GROUP BY u.cd_uf, u.nm_uf, u.sigla_uf, u.area_km2 ORDER BY total_municipios DESC"},
    {"question": "Liste os municípios do MS com a sigla do estado",
     "sql": "SELECT m.cd_mun, m.nm_mun, u.sigla_uf, m.area_km2 FROM br_municipios_2023 m JOIN br_uf_2023 u ON m.cd_uf = u.cd_uf WHERE u.sigla_uf = 'MS' ORDER BY m.nm_mun"},
    {"question": "Qual o percentual de área que cada estado ocupa na região Centro-oeste?",
     "sql": "SELECT nm_uf, sigla_uf, area_km2, ROUND((area_km2 / SUM(area_km2) OVER () * 100)::numeric, 2) AS pct_regiao FROM br_uf_2023 WHERE nm_regiao = 'Centro-oeste' ORDER BY area_km2 DESC"},
]


def init_training():
    global training_examples
    # Carrega do arquivo se existir
    if os.path.exists(TRAINING_FILE):
        try:
            with open(TRAINING_FILE, "r", encoding="utf-8") as f:
                training_examples = json.load(f)
            print(f" {len(training_examples)} exemplos de treinamento carregados de '{TRAINING_FILE}'")
            return
        except Exception:
            pass
    # Primeira execução: usa os defaults e salva
    training_examples = DEFAULT_EXAMPLES[:]
    with open(TRAINING_FILE, "w", encoding="utf-8") as f:
        json.dump(training_examples, f, ensure_ascii=False, indent=2)
    print(f" {len(training_examples)} exemplos de treinamento inicializados em '{TRAINING_FILE}'")

init_training()


# ─────────────────────────────────────────────────────────────────────────────
# POST /train — adiciona ou atualiza um par pergunta→SQL
# GET  /train — lista todos os exemplos salvos
# DELETE /train — remove um exemplo pela pergunta
# ─────────────────────────────────────────────────────────────────────────────
class TrainRequest(BaseModel):
    question: str
    sql: str

@app.post("/train")
def train_add(body: TrainRequest):
    global training_examples
    q   = body.question.strip()
    sql = body.sql.strip().rstrip(";")
    if not q or not sql:
        raise HTTPException(status_code=400, detail="'question' e 'sql' são obrigatórios.")
    for ex in training_examples:
        if ex["question"].strip().lower() == q.lower():
            ex["sql"] = sql
            with open(TRAINING_FILE, "w", encoding="utf-8") as f:
                json.dump(training_examples, f, ensure_ascii=False, indent=2)
            return {"status": "updated", "total": len(training_examples)}
    training_examples.append({"question": q, "sql": sql})
    with open(TRAINING_FILE, "w", encoding="utf-8") as f:
        json.dump(training_examples, f, ensure_ascii=False, indent=2)
    return {"status": "added", "total": len(training_examples)}

@app.get("/train")
def train_list():
    return {"examples": training_examples, "total": len(training_examples)}

class TrainDeleteRequest(BaseModel):
    question: str

@app.delete("/train")
def train_delete(body: TrainDeleteRequest):
    global training_examples
    before = len(training_examples)
    training_examples = [e for e in training_examples
                         if e["question"].strip().lower() != body.question.strip().lower()]
    if len(training_examples) == before:
        raise HTTPException(status_code=404, detail="Exemplo não encontrado.")
    with open(TRAINING_FILE, "w", encoding="utf-8") as f:
        json.dump(training_examples, f, ensure_ascii=False, indent=2)
    return {"status": "deleted", "total": len(training_examples)}

# ─────────────────────────────────────────────────────────────────────────────
# Inicia o servidor
# ─────────────────────────────────────────────────────────────────────────────
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8001)


