# app_rg_vulnerabilidade.py
# Streamlit + Folium — Vulnerabilidade Econômica (Rio Grande - RS)
# Versão: 2025-10-02 (Educação: funcionários por soma das colunas; cards por dependência; fix do mapa quando "Atingidos")

import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os, base64

# ========= Helpers de formatação (pt-BR + K/M/B/T) =========
def _pt_number(x, nd=1):
    s = f"{float(x):,.{nd}f}"
    return s.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")

def br(n, casas=0):
    try: return _pt_number(n, casas)
    except Exception: return str(n)

def compacto_br(n, casas=1):
    try: n = float(n)
    except Exception: return str(n)
    a = abs(n)
    if a >= 1e12: return _pt_number(n/1e12, casas) + " T"
    if a >= 1e9:  return _pt_number(n/1e9,  casas) + " B"
    if a >= 1e6:  return _pt_number(n/1e6,  casas) + " M"
    if a >= 1e3:  return _pt_number(n/1e3,  casas) + " K"
    return br(n, 0)

def formatar_br(valor):
    try: return _pt_number(float(valor), 2)
    except Exception: return str(valor)

def moeda_compacta(n, casas=1):
    return "R$ " + compacto_br(n, casas)

def pct_int(x):
    try: return f"{int(round(float(x)))}%"
    except Exception: return "0%"

# ========= Helpers de contagem =========
def _count_flag01(df, col):
    if (df is None) or (col not in df.columns): return 0
    s = pd.to_numeric(df[col], errors="coerce")
    if s.notna().any(): return int((s == 1).sum())
    sv = df[col].astype(str).str.strip().str.lower()
    return int(sv.isin({"1", "true", "sim", "yes"}).sum())

def _count_equals(df, col, values):
    if (df is None) or (col not in df.columns): return 0
    sv = df[col].astype(str).str.strip().str.lower()
    vals = {str(v).strip().lower() for v in values}
    return int(sv.isin(vals).sum())

# ========= Mapas e helpers específicos: EDUCAÇÃO =========

# Mapeamento de dependência escolar
DEP_MAP = {1: "Federal", 2: "Estadual", 3: "Municipal", 4: "Privada"}
def dep_label(x):
    try:
        v = int(pd.to_numeric(x, errors="coerce"))
        return DEP_MAP.get(v, str(x))
    except Exception:
        return str(x)

# Matrículas por nível — listas de colunas
COLS_INFANTIL = [
    "QT_MAT_INF", "QT_MAT_INF_CRE", "QT_MAT_INF_PRE"
]
COLS_FUNDAMENTAL = [
    "QT_MAT_FUND",
    "QT_MAT_FUND_AI", "QT_MAT_FUND_AI_1", "QT_MAT_FUND_AI_2", "QT_MAT_FUND_AI_3", "QT_MAT_FUND_AI_4", "QT_MAT_FUND_AI_5",
    "QT_MAT_FUND_AF", "QT_MAT_FUND_AF_6", "QT_MAT_FUND_AF_7", "QT_MAT_FUND_AF_8", "QT_MAT_FUND_AF_9"
]
COLS_MEDIO = [
    "QT_MAT_MED",
    "QT_MAT_MED_PROP", "QT_MAT_MED_PROP_1", "QT_MAT_MED_PROP_2", "QT_MAT_MED_PROP_3", "QT_MAT_MED_PROP_4", "QT_MAT_MED_PROP_NS",
    "QT_MAT_MED_CT", "QT_MAT_MED_CT_1", "QT_MAT_MED_CT_2", "QT_MAT_MED_CT_3", "QT_MAT_MED_CT_4", "QT_MAT_MED_CT_NS",
    "QT_MAT_MED_NM", "QT_MAT_MED_NM_1", "QT_MAT_MED_NM_2", "QT_MAT_MED_NM_3", "QT_MAT_MED_NM_4"
]

# Funcionários = soma destas colunas (com 88888 tratado como inválido/zero)
STAFF_COLS = [
    "QT_PROF_ADMINISTRATIVOS","QT_PROF_SERVICOS_GERAIS","QT_PROF_BIBLIOTECARIO","QT_PROF_SAUDE","QT_PROF_COORDENADOR",
    "QT_PROF_FONAUDIOLOGO","QT_PROF_NUTRICIONISTA","QT_PROF_PSICOLOGO","QT_PROF_ALIMENTACAO","QT_PROF_PEDAGOGIA",
    "QT_PROF_SECRETARIO","QT_PROF_SEGURANCA","QT_PROF_MONITORES","QT_PROF_GESTAO","QT_PROF_ASSIST_SOCIAL",
    "QT_PROF_TRAD_LIBRAS","QT_PROF_AGRICOLA","QT_PROF_REVISOR_BRAILLE"
]

def _sum_cols(df: pd.DataFrame, cols: list[str]) -> float:
    if df is None or len(df) == 0:
        return 0.0
    use = [c for c in cols if c in df.columns]
    if not use:
        return 0.0
    return pd.to_numeric(df[use].stack(), errors="coerce").fillna(0).sum()

# ========= Ícones customizados (carrega .datauri prontos de .icons) =========
def _icons_path(filename: str) -> str:
    return os.path.join(".icons", filename)

ICONS_PATHS = {
    "PrediosPublicos": _icons_path("Prédios Públicos.png.datauri"),
    "Empresas":        _icons_path("Empresas.png.datauri"),
    "Saude":           _icons_path("Saúde.png.datauri"),
    "Seguranca":       _icons_path("Segurança.png.datauri"),
    "Escola":          _icons_path("Escola.png.datauri"),
}

@st.cache_data(show_spinner=False)
def _icon_data_uri(path: str) -> str | None:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                uri = f.read().strip()
            return uri if uri.startswith("data:image") else None
    except Exception:
        pass
    return None

@st.cache_data(show_spinner=False)
def get_custom_icon(name: str, size=(28,28), anchor="center") -> folium.CustomIcon | None:
    path = ICONS_PATHS.get(name)
    uri  = _icon_data_uri(path) if path else None
    if uri is None:
        return None
    if anchor == "center":
        ax, ay = size[0]//2, size[1]//2
    elif isinstance(anchor, (list, tuple)) and len(anchor) == 2:
        ax, ay = anchor
    else:
        ax, ay = size[0]//2, size[1]//2
    return folium.CustomIcon(icon_image=uri, icon_size=size, icon_anchor=(ax, ay))

# ========= Configuração =========
st.set_page_config(page_title="Vulnerabilidade Econômica - Rio Grande", layout="wide")

st.markdown("""
<style>
div.block-container { padding-top: 1.5rem; padding-bottom: 4.8rem; }
h1 { padding-bottom: 0.5rem; }
[data-testid="stHorizontalBlock"] { gap: 0.75rem; }
[data-testid="stMetric"] { background-color: #FAFAFA; border: 1px solid #EEEEEE; padding: 1rem; border-radius: 0.5rem; }
.sidebar-logo-bottom { position: absolute; bottom: 1rem; left: 0; right: 0; text-align: center; }
.sidebar-logo-bottom img { max-width: 70%; height: auto; display: block; margin: auto; }

:root{ --card-bg:#FFFFFF; --card-br:#CCC; --card-tx:#000; --muted:#000;
       --blue:#247BA0; --green:#2E7D32; --orange:#C25E00; --purple:#6F42C1; --teal:#00695c; --gray:#424242; }
.mini-card{ display:flex; gap:.65rem; align-items:flex-start; width:100%;
            background:var(--card-bg); border:1px solid var(--card-br);
            border-radius:.6rem; padding:.75rem .95rem !important; margin-bottom:.85rem !important;
            box-shadow:0 2px 6px rgba(0,0,0,.04); }
.mini-card:hover{ border-color:#999; box-shadow:0 4px 10px rgba(0,0,0,.08); }
.accent{width:4px; border-radius:.55rem; margin-right:.5rem; flex:0 0 4px;}
.accent.blue{background:var(--blue);} .accent.green{background:var(--green);} 
.accent.orange{background:var(--orange);} .accent.purple{background:var(--purple);} 
.accent.teal{background:var(--teal);} .accent.gray{background:var(--gray);}
.mini-wrap{display:flex; flex-direction:column; gap:.22rem; width:100%;}
.mini-label{font-size:.85rem; color:var(--muted); font-weight:600;}
.mini-top{display:flex; align-items:center; gap:.55rem;}
.mini-icon{font-size:1.15rem; line-height:1;}
.mini-value{font-size:1.55rem; font-weight:750; color:#000;}

.painel-sec-titulo{margin:.45rem 0 .6rem 0; font-size:1rem; font-weight:700; color:#000;}
.footer-bar {
  position: fixed; right: 0; bottom: 0; background: #FFFFFF;
  border-top: 1px solid #EAEAEA; box-shadow: 0 -2px 10px rgba(0,0,0,0.06);
  z-index: 10050; padding: 6px 20px; font-size: 10pt; color: #555; text-align: right; width: 100%;
}
            
.sidebar-logo-bottom { 
  position: absolute; bottom: 1rem; left: 0; right: 0; 
  text-align: center;
}
.sidebar-logo-bottom img { 
  max-width: 70%; height: auto; display: block; margin: auto;
}
</style>
""", unsafe_allow_html=True)

st.title("🌊 Vulnerabilidade Econômica a Desastres Hidrológicos em Rio Grande")

# ========= I/O =========
@st.cache_data
def carregar_shapefile(caminho_completo):
    gdf = gpd.read_file(caminho_completo, encoding='utf-8')
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    return gdf

@st.cache_data
def carregar_empresas_xlsx(caminho_completo):
    try:
        df = pd.read_excel(caminho_completo)
        if 'latitude' in df.columns and 'longitude' in df.columns:
            df['latitude']  = pd.to_numeric(df['latitude'],  errors='coerce')
            df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
            df.dropna(subset=['latitude','longitude'], inplace=True)
        return gpd.GeoDataFrame(df,
                                geometry=gpd.points_from_xy(df.longitude, df.latitude),
                                crs="EPSG:4326")
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo de empresas: {e}")
        return None

# === SAÚDE ===
@st.cache_data
def carregar_saude_xlsx(caminho_completo):
    try:
        df = pd.read_excel(caminho_completo)
        df.columns = [str(c).strip() for c in df.columns]
        rename_map = {}
        for c in df.columns:
            if c.strip().lower() == 'co_municipio_gestor':
                rename_map[c] = 'CO_MUNICIPIO_GESTOR'
        if rename_map:
            df = df.rename(columns=rename_map)

        required = [
            'CO_UNIDADE','CO_CNES','NU_CNPJ_MANTENEDORA','TP_PFPJ','NIVEL_DEP','NO_RAZAO_SOCIAL',
            'NO_FANTASIA','NO_LOGRADOURO','NU_ENDERECO','NO_COMPLEMENTO','NO_BAIRRO','CO_CEP',
            'CO_MUNICIPIO_GESTOR','Latitude','Longitude','CO_TIPO_ESTABELECIMENTO'
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Colunas ausentes em Saúde.xlsx: {missing}")

        df['Latitude']  = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df.dropna(subset=['Latitude','Longitude'], inplace=True)

        gdf = gpd.GeoDataFrame(
            df.copy(),
            geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']),
            crs='EPSG:4326'
        )
        return gdf
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo de Saúde: {e}")
        return None

# === PRÉDIOS PÚBLICOS ===
@st.cache_data
def carregar_predios_publicos_xlsx(caminho_completo):
    try:
        df = pd.read_excel(caminho_completo)
        df.columns = [str(c).strip() for c in df.columns]
        req = ['Nome','Latitude','Longitude']
        miss = [c for c in req if c not in df.columns]
        if miss:
            raise ValueError(f"Colunas ausentes em Prédios Públicos: {miss}")
        df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df = df.dropna(subset=['Latitude','Longitude']).copy()
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']),
            crs="EPSG:4326"
        )
        return gdf
    except Exception as e:
        st.error(f"Erro ao carregar Prédios Públicos: {e}")
        return None

# === SEGURANÇA ===
@st.cache_data
def carregar_seguranca_xlsx(caminho_completo):
    try:
        df = pd.read_excel(caminho_completo)
        df.columns = [str(c).strip() for c in df.columns]
        req = ['Nome','Latitude','Longitude']
        miss = [c for c in req if c not in df.columns]
        if miss:
            raise ValueError(f"Colunas ausentes em Segurança: {miss}")
        df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df = df.dropna(subset=['Latitude','Longitude']).copy()
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']),
            crs="EPSG:4326"
        )
        return gdf
    except Exception as e:
        st.error(f"Erro ao carregar Segurança: {e}")
        return None

# === EDUCAÇÃO ===
@st.cache_data
def carregar_educacao_xlsx(caminho_completo: str) -> gpd.GeoDataFrame | None:
    """
    Carrega 'Escolas.xlsx' e prepara a camada de Educação:
      - Garante colunas essenciais e coordenadas válidas (Latitude/Longitude).
      - Converte colunas numéricas; nas colunas de funcionários, o valor 88888 é tratado como sentinela inválida (vira 0).
      - Calcula DEP_LABEL (TP_DEPENDENCIA -> {1: Federal, 2: Estadual, 3: Municipal, 4: Privada}).
      - Calcula QT_FUNCIONARIOS = soma(STAFF_COLS) já sem os 88888.
      - Retorna GeoDataFrame em EPSG:4326 com geometry = Point(Longitude, Latitude).
    """
    try:
        df = pd.read_excel(caminho_completo)
        df.columns = [str(c).strip() for c in df.columns]

        # Checagem de colunas mínimas
        req = ["Latitude", "Longitude", "NO_ENTIDADE", "TP_DEPENDENCIA"]
        faltando = [c for c in req if c not in df.columns]
        if faltando:
            raise ValueError(f"Colunas ausentes em Escolas.xlsx: {faltando}")

        # Coordenadas
        df["Latitude"]  = pd.to_numeric(df["Latitude"], errors="coerce")
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
        df = df.dropna(subset=["Latitude", "Longitude"]).copy()

        # Rótulo de dependência
        df["DEP_LABEL"] = df["TP_DEPENDENCIA"].apply(dep_label)

        # Converte matrículas e base/prof para numérico (mantém NaN onde não for possível)
        cols_to_numeric = set(COLS_INFANTIL + COLS_FUNDAMENTAL + COLS_MEDIO + ["QT_MAT_BAS", "QT_MAT_PROF"])
        for c in cols_to_numeric:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # Converte colunas de funcionários p/ numérico e zera sentinela 88888
        for c in STAFF_COLS:
            if c in df.columns:
                s = pd.to_numeric(df[c], errors="coerce")
                # 88888 é inválido -> 0
                s = s.mask(s == 88888, 0)
                df[c] = s.fillna(0)

        # QT_FUNCIONARIOS = soma das STAFF_COLS (já sem 88888)
        presentes = [c for c in STAFF_COLS if c in df.columns]
        df["QT_FUNCIONARIOS"] = df[presentes].sum(axis=1).fillna(0) if presentes else 0

        # GeoDataFrame
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
            crs="EPSG:4326"
        )
        return gdf

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo de Educação (Escolas.xlsx): {e}")
        return None
    
# ========================= Carregamento dos dados =========================
with st.spinner('Carregando dados geoespaciais...'):
    pasta_dados = "Dados"
    gpea_logo_path = "GPEA.png"

    bairros_gdf         = carregar_shapefile(os.path.join(pasta_dados, 'PMRG_231215_layer_Bairros.shp'))
    logradouros_gdf     = carregar_shapefile(os.path.join(pasta_dados, 'PMRG_231215_layer_Logradouros_segmentos.shp'))
    mancha_mai2024_gdf  = carregar_shapefile(os.path.join(pasta_dados, 'CEN_MAI2024.shp'))
    mancha_set2023_gdf  = carregar_shapefile(os.path.join(pasta_dados, 'CEN_SET2023.shp'))

    plus60_path = os.path.join(pasta_dados, 'CEN_MAI24_MAIS60CM.shp')
    mancha_mai2024_plus60_gdf = carregar_shapefile(plus60_path) if os.path.exists(plus60_path) else None
    if mancha_mai2024_plus60_gdf is None:
        st.warning("Camada 'CEN_MAI24_MAIS60CM.shp' não encontrada na pasta 'Dados/'.")

    quadras_gdf         = carregar_shapefile(os.path.join(pasta_dados, 'PMRG_231215_layer_Quadras.shp'))
    terrenos_gdf        = carregar_shapefile(os.path.join(pasta_dados, 'PMRG_231215_layer_Terrenos.shp'))
    empresas_gdf        = carregar_empresas_xlsx(os.path.join(pasta_dados, 'RAIS e Receita (Georrefenciada).xlsx'))
    imoveis_gdf         = carregar_shapefile(os.path.join(pasta_dados, 'PMRG_CAD_IMOB.shp'))

    if imoveis_gdf is not None and (imoveis_gdf.crs is None or imoveis_gdf.crs.to_epsg() in [None, 4326]):
        imoveis_gdf = imoveis_gdf.set_crs("EPSG:31982", allow_override=True)

    # === SAÚDE ===
    saude_gdf = None
    for _p in [os.path.join(pasta_dados, 'Saúde.xlsx'),
               os.path.join(pasta_dados, 'Saude.xlsx')]:
        if os.path.exists(_p):
            saude_gdf = carregar_saude_xlsx(_p)
            if saude_gdf is not None: break
    if saude_gdf is None:
        st.warning("Planilha de Saúde não encontrada. Verifique o caminho e o nome do arquivo (Saúde.xlsx).")

    # === PRÉDIOS PÚBLICOS ===
    predios_publicos_gdf = None
    for _p in [os.path.join(pasta_dados, 'parcial prédios públicos.xlsx'),
               os.path.join(pasta_dados, 'parcial predios publicos.xlsx'),
               '/mnt/data/parcial prédios públicos.xlsx']:
        if os.path.exists(_p):
            predios_publicos_gdf = carregar_predios_publicos_xlsx(_p)
            if predios_publicos_gdf is not None: break
    if predios_publicos_gdf is None:
        st.warning("Planilha de Prédios Públicos não encontrada. Esperado: 'parcial prédios públicos.xlsx'.")

    # === SEGURANÇA ===
    seguranca_gdf = None
    for _p in [os.path.join(pasta_dados, 'parcial segurança.xlsx'),
               os.path.join(pasta_dados, 'parcial seguranca.xlsx'),
               '/mnt/data/parcial segurança.xlsx']:
        if os.path.exists(_p):
            seguranca_gdf = carregar_seguranca_xlsx(_p)
            if seguranca_gdf is not None: break
    if seguranca_gdf is None:
        st.warning("Planilha de Segurança não encontrada. Esperado: 'parcial segurança.xlsx'.")

    # === EDUCAÇÃO ===
    educacao_gdf = None
    for _p in [
        r"G:\Meu Drive\PFP II\PROJ_RG_INUND_2025\Dados\Escolas.xlsx",
        os.path.join(pasta_dados, "Escolas.xlsx")
    ]:
        if os.path.exists(_p):
            educacao_gdf = carregar_educacao_xlsx(_p)
            if educacao_gdf is not None:
                break
    if educacao_gdf is None:
        st.warning("Planilha de Educação não encontrada. Esperado: 'Escolas.xlsx'.")

# ========= Sidebar =========
st.sidebar.image(gpea_logo_path, use_container_width=True)

# ---- Estado inicial das checkboxes do Controle de Camadas ----
for _k in ("ck_empresas","ck_saude","ck_educacao","ck_predios","ck_seguranca"):
    if _k not in st.session_state:
        st.session_state[_k] = False

# ---- Cenários ----
st.sidebar.header("Cenários")
opcoes_manchas = {
    "Maio de 2024":        mancha_mai2024_gdf,
    "Maio de 2024 +60CM":  mancha_mai2024_plus60_gdf,
    "Setembro de 2023":    mancha_set2023_gdf,
}
lista_opcoes = list(opcoes_manchas.keys())
selecao_mancha_nome = st.sidebar.selectbox(
    "Selecione o Cenário:", options=lista_opcoes, index=None,
    placeholder="Escolha uma mancha",
    help="Selecione uma mancha para habilitar os filtros de 'Atingidos'."
)
mancha_selecionada_gdf = opcoes_manchas.get(selecao_mancha_nome) if selecao_mancha_nome else None
modo_atingidos = mancha_selecionada_gdf is not None

if modo_atingidos:
    st.sidebar.markdown("**Exibir Camadas Atingidas**")
    opcoes_camadas = ["Empresas", "Saúde", "Educação", "Ruas", "Terrenos", "Quadras", "Imóveis", "Prédios Públicos", "Segurança"]
    selecionadas = st.sidebar.multiselect("Selecione as camadas", opcoes_camadas, default=[])
else:
    selecionadas = []

# ---- Sincroniza seleção de Atingidos -> Controle de Camadas ----
_map_atg_to_ck = {
    "Empresas":         "ck_empresas",
    "Saúde":            "ck_saude",
    "Educação":         "ck_educacao",
    "Prédios Públicos": "ck_predios",
    "Segurança":        "ck_seguranca",
}
for _nome, _ck in _map_atg_to_ck.items():
    if _nome in selecionadas:
        st.session_state[_ck] = True

# ---- Filtros ----
st.sidebar.header("Filtros")

# === Filtros: Empresas ===
empresas_filtradas = empresas_gdf
if empresas_gdf is not None:
    setores_opcoes = sorted(empresas_gdf['Seção'].dropna().unique()) if ('Seção' in empresas_gdf.columns) else []
    setor_selecionado = st.sidebar.multiselect(
        "Setor (Empresas)", options=setores_opcoes, default=[],
        help="Selecione um Setor para habilitar os filtros de 'Subsetor'."
    )
    if setor_selecionado and 'Seção' in empresas_gdf.columns:
        empresas_filtradas = empresas_gdf[empresas_gdf['Seção'].isin(setor_selecionado)].copy()
    else:
        empresas_filtradas = empresas_gdf.copy()

    subsetores_opcoes = []
    subsetor_selecionado = []
    if setor_selecionado and 'Denominação' in empresas_filtradas.columns:
        subsetores_opcoes = sorted(empresas_filtradas['Denominação'].dropna().unique())
        subsetor_selecionado = st.sidebar.multiselect("Subsetor (Empresas)", options=subsetores_opcoes, default=[])
        if subsetor_selecionado:
            empresas_filtradas = empresas_filtradas[empresas_filtradas['Denominação'].isin(subsetor_selecionado)]

    st.sidebar.markdown("Situação Cadastral (Empresas)")
    c1_sc, c2_sc = st.sidebar.columns(2)
    chk_ativa   = c1_sc.checkbox("Ativa", value=True)
    chk_baixada = c2_sc.checkbox("Baixada", value=False)
    if 'situacao_cadastral_desc' in empresas_filtradas.columns:
        if chk_ativa or chk_baixada:
            selecao_situacao = []
            if chk_ativa:   selecao_situacao.append("Ativa")
            if chk_baixada: selecao_situacao.append("Baixada")
            empresas_filtradas = empresas_filtradas[empresas_filtradas['situacao_cadastral_desc'].isin(selecao_situacao)]

# === Filtros: Saúde ===
saude_filtrada = saude_gdf
if saude_gdf is not None:
    tipos_opcoes = sorted(saude_gdf['CO_TIPO_ESTABELECIMENTO'].dropna().astype(str).unique()) if 'CO_TIPO_ESTABELECIMENTO' in saude_gdf.columns else []
    tipos_sel = st.sidebar.multiselect("Tipo do Estabelecimento (Saúde)", options=tipos_opcoes, default=[])
    if tipos_sel:
        saude_filtrada = saude_gdf[saude_gdf['CO_TIPO_ESTABELECIMENTO'].astype(str).isin(tipos_sel)].copy()
    else:
        saude_filtrada = saude_gdf.copy()

# === Filtros: Prédios Públicos ===
predios_filtrados = predios_publicos_gdf
if predios_publicos_gdf is not None:
    col_tipo = 'Tipo' if 'Tipo' in predios_publicos_gdf.columns else None
    if col_tipo:
        tipos_pp = sorted(predios_publicos_gdf[col_tipo].dropna().astype(str).unique())
        tipos_pp_sel = st.sidebar.multiselect("Tipo (Prédios Públicos)", options=tipos_pp, default=[])
        if tipos_pp_sel:
            predios_filtrados = predios_publicos_gdf[predios_publicos_gdf[col_tipo].astype(str).isin(tipos_pp_sel)].copy()
        else:
            predios_filtrados = predios_publicos_gdf.copy()

# === Filtros: Segurança ===
seguranca_filtrada = seguranca_gdf
if seguranca_gdf is not None:
    col_tipo_s = 'Tipo' if 'Tipo' in seguranca_gdf.columns else None
    if col_tipo_s:
        tipos_s = sorted(seguranca_gdf[col_tipo_s].dropna().astype(str).unique())
        tipos_s_sel = st.sidebar.multiselect("Tipo (Segurança)", options=tipos_s, default=[])
        if tipos_s_sel:
            seguranca_filtrada = seguranca_gdf[seguranca_gdf[col_tipo_s].astype(str).isin(tipos_s_sel)].copy()
        else:
            seguranca_filtrada = seguranca_gdf.copy()

# === Filtros: Educação (Dependência) ===
educacao_filtrada = educacao_gdf
if educacao_gdf is not None:
    dep_opcoes = sorted(educacao_gdf["DEP_LABEL"].dropna().unique())
    dep_sel = st.sidebar.multiselect(
        "Dependência (Educação)", options=dep_opcoes, default=[],
        help="Filtra escolas por dependência administrativa (Federal/Estadual/Municipal/Privada)."
    )
    if dep_sel:
        educacao_filtrada = educacao_gdf[educacao_gdf["DEP_LABEL"].isin(dep_sel)].copy()
    else:
        educacao_filtrada = educacao_gdf.copy()

# ---- Controle de Camadas ----
st.sidebar.header("Controle de Camadas")
c3_sc, c4_sc = st.sidebar.columns(2)
mostrar_empresas  = c3_sc.checkbox("Empresas", key="ck_empresas")
mostrar_saude     = c4_sc.checkbox("Saúde", key="ck_saude")
c5_sc, c6_sc = st.sidebar.columns(2)
mostrar_educacao  = c5_sc.checkbox("Educação", key="ck_educacao")
mostrar_predios   = c6_sc.checkbox("Prédios Públicos", key="ck_predios")
c7_sc, c8_sc = st.sidebar.columns(2)
mostrar_seguranca = c7_sc.checkbox("Segurança", key="ck_seguranca")

# ---- Flags das camadas atingidas ----
mostrar_empresas_atingidas  = ("Empresas" in selecionadas) and modo_atingidos
mostrar_saude_atingida      = ("Saúde"    in selecionadas) and modo_atingidos
mostrar_educacao_atingida   = ("Educação" in selecionadas) and modo_atingidos
mostrar_ruas_atingidas      = ("Ruas"     in selecionadas) and modo_atingidos
mostrar_terrenos_atingidos  = ("Terrenos" in selecionadas) and modo_atingidos
mostrar_quadras_atingidas   = ("Quadras"  in selecionadas) and modo_atingidos
mostrar_imoveis_atingidos   = ("Imóveis"  in selecionadas) and modo_atingidos
mostrar_predios_atingidos   = ("Prédios Públicos" in selecionadas) and modo_atingidos
mostrar_seguranca_atingida  = ("Segurança" in selecionadas) and modo_atingidos

# --- Sidebar: logo do CIEX no rodapé ---
st.sidebar.markdown('<div class="sidebar-logo-bottom">', unsafe_allow_html=True)
try:
    ciex_logo_path = "CIEX.png"
    if os.path.exists(ciex_logo_path):
        with open(ciex_logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        st.sidebar.markdown(
            f"""<div style="width:100%; display:flex; justify-content:center; align-items:center;">
                    <img src="data:image/png;base64,{b64}" alt="CIEX" />
                </div>""",
            unsafe_allow_html=True
        )
    else:
        st.sidebar.caption("Logo do CIEX não encontrada (CIEX.png).")
except Exception as e:
    st.sidebar.caption(f"Não foi possível carregar a logo do CIEX: {e}")
st.sidebar.markdown('</div>', unsafe_allow_html=True)

# ========= Cálculos espaciais =========
def _clean_mancha(gdf):
    if gdf is None or len(gdf) == 0:
        return None
    try:
        m = gdf.copy()
        if m.crs is None:
            m = m.set_crs("EPSG:4326", allow_override=True)
        m = m.to_crs("EPSG:4326")
        try:
            m["geometry"] = m.buffer(0)
        except Exception:
            pass
        m = m[~m.geometry.is_empty & m.geometry.notna()]
        union_geom = m.unary_union
        m = gpd.GeoDataFrame(geometry=[union_geom], crs="EPSG:4326")
        if len(m) == 0:
            return None
        return m
    except Exception:
        return None

def _sjoin_points_with_fallback(points_gdf, poly_gdf):
    if points_gdf is None or poly_gdf is None or len(points_gdf) == 0 or len(poly_gdf) == 0:
        return None
    try:
        p4326 = points_gdf.to_crs("EPSG:4326")
        res = gpd.sjoin(p4326, poly_gdf, how="inner", predicate="within")
        if res is not None and len(res) > 0:
            return res
        res2 = gpd.sjoin(p4326, poly_gdf, how="inner", predicate="intersects")
        return res2 if res2 is not None and len(res2) > 0 else res
    except Exception:
        try:
            p4326 = points_gdf.to_crs("EPSG:4326")
            return gpd.sjoin(p4326, poly_gdf, how="inner", predicate="intersects")
        except Exception:
            return None

def _sjoin_lines_or_polys(layer_gdf, poly_gdf):
    if layer_gdf is None or poly_gdf is None or len(layer_gdf) == 0 or len(poly_gdf) == 0:
        return None
    try:
        l4326 = layer_gdf.to_crs("EPSG:4326")
        return gpd.sjoin(l4326, poly_gdf, how="inner", predicate="intersects")
    except Exception:
        return None

mancha_4326 = _clean_mancha(mancha_selecionada_gdf) if mancha_selecionada_gdf is not None else None

# Empresas x mancha
empresas_atingidas_gdf = _sjoin_points_with_fallback(empresas_filtradas, mancha_4326) if (empresas_filtradas is not None and mancha_4326 is not None) else None
# Saúde x mancha
saude_atingida_gdf = _sjoin_points_with_fallback(saude_filtrada, mancha_4326) if (saude_filtrada is not None and mancha_4326 is not None) else None
# Ruas x mancha
if logradouros_gdf is not None:
    logradouros_gdf = logradouros_gdf.copy()
    if {'tipo','nome'}.issubset(logradouros_gdf.columns):
        logradouros_gdf['tipo'] = logradouros_gdf['tipo'].fillna('')
        logradouros_gdf['nome'] = logradouros_gdf['nome'].fillna('')
        logradouros_gdf['_rua_id_interno'] = (logradouros_gdf['tipo'].astype(str).str.strip() + ' ' +
                                              logradouros_gdf['nome'].astype(str).str.strip()).str.strip()
    else:
        logradouros_gdf['_rua_id_interno'] = logradouros_gdf.index.astype(str)
logradouros_atingidos_gdf = _sjoin_lines_or_polys(logradouros_gdf, mancha_4326) if (logradouros_gdf is not None and mancha_4326 is not None) else None
# Terrenos x mancha
total_terrenos = len(terrenos_gdf) if terrenos_gdf is not None else 0
terrenos_atingidos_gdf = _sjoin_lines_or_polys(terrenos_gdf, mancha_4326) if (terrenos_gdf is not None and mancha_4326 is not None) else None
# Quadras x mancha
total_quadras = len(quadras_gdf) if quadras_gdf is not None else 0
quadras_atingidas_gdf = _sjoin_lines_or_polys(quadras_gdf, mancha_4326) if (quadras_gdf is not None and mancha_4326 is not None) else None
# Imóveis x mancha
def _to_point_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gdf
    geom = gdf.geometry
    pts = geom if geom.iloc[0].geom_type == "Point" else geom.representative_point()
    return gpd.GeoDataFrame(gdf.drop(columns="geometry"), geometry=pts, crs=gdf.crs)
imoveis_atingidos_gdf = None
total_imoveis = len(imoveis_gdf) if imoveis_gdf is not None else 0
if (imoveis_gdf is not None) and (mancha_4326 is not None):
    imoveis_pts = _to_point_gdf(imoveis_gdf)
    imoveis_atingidos_gdf = _sjoin_points_with_fallback(imoveis_pts, mancha_4326)
# Prédios Públicos x mancha
predios_atingidos_gdf = _sjoin_points_with_fallback(predios_filtrados, mancha_4326) if (predios_filtrados is not None and mancha_4326 is not None) else None
# Segurança x mancha
seguranca_atingida_gdf = _sjoin_points_with_fallback(seguranca_filtrada, mancha_4326) if (seguranca_filtrada is not None and mancha_4326 is not None) else None
# Educação x mancha
educacao_atingida_gdf = _sjoin_points_with_fallback(educacao_filtrada, mancha_4326) if (educacao_filtrada is not None and mancha_4326 is not None) else None

# ====== PAINEL DE IMPACTO ======
with st.expander("📊 Painel de Impacto", expanded=False):

    def mini_card(col, titulo, valor, delta=None, icon="📊", accent="blue"):
        delta_html = f'<div class="mini-delta">{delta}</div>' if delta else ''
        col.markdown(
            f"""
            <div class="mini-card">
              <div class="accent {accent}"></div>
              <div class="mini-wrap">
                <div class="mini-label">{titulo}</div>
                <div class="mini-top">
                  <span class="mini-icon">{icon}</span>
                  <span class="mini-value">{valor}</span>
                </div>
                {delta_html}
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.subheader(f"Impacto: {selecao_mancha_nome}" if modo_atingidos else "Impacto")

    # ---------- EMPRESAS ----------
    total_empresas = len(empresas_filtradas) if empresas_filtradas is not None else 0
    total_empregados = (empresas_filtradas['Empregados'].sum()
                        if (empresas_filtradas is not None and 'Empregados' in empresas_filtradas.columns) else 0)
    total_massa_salarial = (empresas_filtradas['Massa_Salarial'].sum()
                            if (empresas_filtradas is not None and 'Massa_Salarial' in empresas_filtradas.columns) else 0)
    media_salarial_geral = (empresas_filtradas['MédiaSalarial'].mean()
                            if (empresas_filtradas is not None and 'MédiaSalarial' in empresas_filtradas.columns) else 0)

    if modo_atingidos and (empresas_atingidas_gdf is not None) and (not empresas_atingidas_gdf.empty):
        ating_empresas = len(empresas_atingidas_gdf)
        ating_empregados = int(empresas_atingidas_gdf['Empregados'].sum() or 0) if 'Empregados' in empresas_atingidas_gdf.columns else 0
        ating_massa = float(empresas_atingidas_gdf['Massa_Salarial'].sum() or 0) if 'Massa_Salarial' in empresas_atingidas_gdf.columns else 0.0
        media_salarial_atingida = float(empresas_atingidas_gdf['MédiaSalarial'].mean() or 0) if 'MédiaSalarial' in empresas_atingidas_gdf.columns else 0.0
    else:
        ating_empresas = ating_empregados = 0
        ating_massa = media_salarial_atingida = 0.0

    perc_empresas   = (ating_empresas   / total_empresas * 100)       if total_empresas       > 0 else 0
    perc_empregados = (ating_empregados / total_empregados * 100)     if total_empregados     > 0 else 0
    perc_massa      = (ating_massa      / total_massa_salarial * 100) if total_massa_salarial > 0 else 0

    st.markdown('<div class="painel-sec-titulo">Empresas</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    if mostrar_empresas_atingidas:
        mini_card(c1, "Empresas Atingidas", compacto_br(ating_empresas),
                  f"de {compacto_br(total_empresas)} ({pct_int(perc_empresas)})", icon="🏢", accent="blue")
        mini_card(c2, "Empregados Atingidos", compacto_br(ating_empregados),
                  f"de {compacto_br(total_empregados)} ({pct_int(perc_empregados)})", icon="👥", accent="blue")
        mini_card(c3, "Massa Salarial Atingida", moeda_compacta(ating_massa),
                  f"de {moeda_compacta(total_massa_salarial)} ({pct_int(perc_massa)})", icon="💰", accent="blue")
        mini_card(c4, "Média Salarial (Atingidos)", moeda_compacta(media_salarial_atingida),
                  f"de {formatar_br(media_salarial_geral)} no Total", icon="📈", accent="blue")
    else:
        mini_card(c1, "Empresas (Total)", compacto_br(total_empresas), icon="🏢", accent="blue")
        mini_card(c2, "Empregados (Total)", compacto_br(total_empregados), icon="👥", accent="blue")
        mini_card(c3, "Massa Salarial (Total)", moeda_compacta(total_massa_salarial), icon="💰", accent="blue")
        mini_card(c4, "Média Salarial (Total)", moeda_compacta(media_salarial_geral), icon="📈", accent="blue")

    # ---------- SAÚDE ----------
    st.markdown('<div class="painel-sec-titulo">Saúde</div>', unsafe_allow_html=True)

    def _saude_cards_por_tipo(saude_total_gdf, saude_atg_gdf, mostrar_atingidos: bool, max_cards: int = 8):
        if saude_total_gdf is None or len(saude_total_gdf) == 0:
            st.info("Sem registros de Saúde para exibir.")
            return
        col_tipo = 'CO_TIPO_ESTABELECIMENTO'
        cont_total = saude_total_gdf[col_tipo].astype(str).value_counts().reset_index()
        cont_total.columns = [col_tipo, 'Total']
        if mostrar_atingidos and (saude_atg_gdf is not None) and (len(saude_atg_gdf) > 0):
            cont_atg = saude_atg_gdf[col_tipo].astype(str).value_counts().reset_index()
            cont_atg.columns = [col_tipo, 'Atingidos']
        else:
            cont_atg = pd.DataFrame(columns=[col_tipo, 'Atingidos'])
        dfm = cont_total.merge(cont_atg, on=col_tipo, how='left')
        dfm['Atingidos'] = dfm['Atingidos'].fillna(0).astype(int)
        dfm['%'] = (dfm['Atingidos'] / dfm['Total'] * 100).fillna(0)
        dfm = dfm.sort_values(['Total', col_tipo], ascending=[False, True]).reset_index(drop=True)
        top = dfm.head(max_cards)
        n = len(top)
        for i in range(0, n, 4):
            cols = st.columns(min(4, n - i))
            for j, (_, row) in enumerate(top.iloc[i:i+4].iterrows()):
                tipo = str(row[col_tipo]); total = int(row['Total']); ating = int(row['Atingidos'])
                delta = f"de {compacto_br(total)} ({pct_int((ating/total*100) if total else 0)})" if mostrar_atingidos else None
                valor = compacto_br(ating) if mostrar_atingidos else compacto_br(total)
                mini_card(cols[j], f"{tipo}", valor, delta=delta, icon="🏥", accent="green")
        if len(dfm) > max_cards:
            with st.expander("Outros tipos de estabelecimento (tabela)", expanded=False):
                st.dataframe(
                    dfm.rename(columns={col_tipo: "Tipo", "Total": "Total", "Atingidos": "Atingidos", "%": "% ating."}),
                    use_container_width=True, hide_index=True
                )

    _saude_cards_por_tipo(saude_filtrada, saude_atingida_gdf, mostrar_saude_atingida, max_cards=8)

    if mostrar_saude_atingida and (saude_atingida_gdf is not None) and (not saude_atingida_gdf.empty):
        with st.expander("📋 Unidades de Saúde Atingidas", expanded=False):
            tmp = saude_atingida_gdf.copy()
            vis_cols, aliases = [], []
            for col, alias in [("NO_FANTASIA", "Nome"), ("NO_BAIRRO", "Bairro"), ("NO_LOGRADOURO", "Logradouro"), ("NU_ENDERECO", "Número")]:
                if col in tmp.columns:
                    vis_cols.append(col); aliases.append(alias)
            if not vis_cols:
                tmp["_idx"] = tmp.index.astype(str)
                vis_cols = ["_idx"]; aliases = ["ID"]
            st.dataframe(
                tmp[vis_cols].rename(columns=dict(zip(vis_cols, aliases))),
                use_container_width=True, hide_index=True
            )

    # ---------- EDUCAÇÃO ----------
    st.markdown('<div class="painel-sec-titulo">Educação</div>', unsafe_allow_html=True)

# Totais
    total_escolas = len(educacao_filtrada) if educacao_filtrada is not None else 0
# Funcionários (já com 88888 zerado no carregamento)
    total_func = float(educacao_filtrada["QT_FUNCIONARIOS"].sum()) if (educacao_filtrada is not None and "QT_FUNCIONARIOS" in educacao_filtrada.columns) else 0.0

# Matrículas por nível
    total_inf  = _sum_cols(educacao_filtrada, COLS_INFANTIL)        # Educação Infantil
    total_fund = _sum_cols(educacao_filtrada, COLS_FUNDAMENTAL)     # Ensino Fundamental
    total_med  = _sum_cols(educacao_filtrada, COLS_MEDIO)           # Ensino Médio
    total_tec  = float(pd.to_numeric(educacao_filtrada["QT_MAT_PROF"], errors="coerce").fillna(0).sum()) if (educacao_filtrada is not None and "QT_MAT_PROF" in educacao_filtrada.columns) else 0.0

# Atingidos
    if modo_atingidos and (educacao_atingida_gdf is not None) and (not educacao_atingida_gdf.empty):
        ating_escolas = len(educacao_atingida_gdf)
        ating_func    = float(educacao_atingida_gdf["QT_FUNCIONARIOS"].sum()) if "QT_FUNCIONARIOS" in educacao_atingida_gdf.columns else 0.0

        ating_inf  = _sum_cols(educacao_atingida_gdf, COLS_INFANTIL)
        ating_fund = _sum_cols(educacao_atingida_gdf, COLS_FUNDAMENTAL)
        ating_med  = _sum_cols(educacao_atingida_gdf, COLS_MEDIO)
        ating_tec  = float(pd.to_numeric(educacao_atingida_gdf["QT_MAT_PROF"], errors="coerce").fillna(0).sum()) if "QT_MAT_PROF" in educacao_atingida_gdf.columns else 0.0
    else:
        ating_escolas = 0
        ating_func = 0.0
        ating_inf = ating_fund = ating_med = ating_tec = 0.0

# Percentuais
    perc_escolas = (ating_escolas / total_escolas * 100) if total_escolas > 0 else 0
    perc_func    = (ating_func    / total_func    * 100) if total_func    > 0 else 0
    perc_inf     = (ating_inf     / total_inf     * 100) if total_inf     > 0 else 0
    perc_fund    = (ating_fund    / total_fund    * 100) if total_fund    > 0 else 0
    perc_med     = (ating_med     / total_med     * 100) if total_med     > 0 else 0
    perc_tec     = (ating_tec     / total_tec     * 100) if total_tec     > 0 else 0

# Linha 1: escolas e funcionários (síntese)
    e_top1, e_top2 = st.columns(2)
    if mostrar_educacao_atingida:
        mini_card(e_top1, "Escolas Atingidas", compacto_br(ating_escolas),
                f"de {compacto_br(total_escolas)} ({pct_int(perc_escolas)})", icon="🏫", accent="teal")
        mini_card(e_top2, "Funcionários Atingidos", compacto_br(ating_func),
                f"de {compacto_br(total_func)} ({pct_int(perc_func)})", icon="👥", accent="teal")
    else:
        mini_card(e_top1, "Escolas (Total)", compacto_br(total_escolas), icon="🏫", accent="teal")
        mini_card(e_top2, "Funcionários (Total)", compacto_br(total_func), icon="👥", accent="teal")

# Linha 2: cards por nível (Infantil, Fundamental, Médio, Técnico/Profissional)
    e1, e2, e3, e4 = st.columns(4)
    if mostrar_educacao_atingida:
        mini_card(e1, "Educação Infantil (Ating.)", compacto_br(ating_inf),
                f"de {compacto_br(total_inf)} ({pct_int(perc_inf)})", icon="🧸", accent="teal")
        mini_card(e2, "Ensino Fundamental (Ating.)", compacto_br(ating_fund),
                f"de {compacto_br(total_fund)} ({pct_int(perc_fund)})", icon="📗", accent="teal")
        mini_card(e3, "Ensino Médio (Ating.)", compacto_br(ating_med),
                f"de {compacto_br(total_med)} ({pct_int(perc_med)})", icon="📘", accent="teal")
        mini_card(e4, "Técnico/Prof. (Ating.)", compacto_br(ating_tec),
                f"de {compacto_br(total_tec)} ({pct_int(perc_tec)})", icon="🛠️", accent="teal")
    else:
        mini_card(e1, "Educação Infantil (Total)", compacto_br(total_inf), icon="🧸", accent="teal")
        mini_card(e2, "Ensino Fundamental (Total)", compacto_br(total_fund), icon="📗", accent="teal")
        mini_card(e3, "Ensino Médio (Total)", compacto_br(total_med), icon="📘", accent="teal")
        mini_card(e4, "Técnico/Prof. (Total)", compacto_br(total_tec), icon="🛠️", accent="teal")

# ---- Cards por dependência escolar (mantidos) ----
    def _cards_dependencia(edu_total, edu_atg, show_ating):
        if edu_total is None or len(edu_total)==0:
            st.info("Sem registros de Educação para exibir por dependência.")
            return
        base = edu_total.groupby("DEP_LABEL", dropna=False).agg(
            Escolas=("DEP_LABEL","size"),
            Funcionarios=("QT_FUNCIONARIOS","sum")
        ).reset_index()
        if show_ating and (edu_atg is not None):
            atg = edu_atg.groupby("DEP_LABEL", dropna=False).agg(
                Escolas=("DEP_LABEL","size"),
                Funcionarios=("QT_FUNCIONARIOS","sum")
            ).reset_index()
            df = base.merge(atg, on="DEP_LABEL", how="left", suffixes=("", "_ATG")).fillna({"Escolas_ATG":0,"Funcionarios_ATG":0})
        else:
            df = base.copy()
            df["Escolas_ATG"] = 0
            df["Funcionarios_ATG"] = 0

        ordem = ["Federal","Estadual","Municipal","Privada"]
        df["__ord"] = df["DEP_LABEL"].apply(lambda x: ordem.index(x) if x in ordem else 999)
        df = df.sort_values(["__ord","DEP_LABEL"]).drop(columns="__ord")

        cols = st.columns(4)
        for i, (_, r) in enumerate(df.iterrows()):
            titulo = r["DEP_LABEL"]
            if show_ating:
                delta_txt = f"{int(r['Escolas_ATG'])} esc. / {compacto_br(r['Funcionarios_ATG'])} func. ating."
                valor_txt = f"{int(r['Escolas'])} / {compacto_br(r['Funcionarios'])}"
                mini_card(cols[i], titulo, valor_txt, delta=delta_txt, icon="🏫", accent="teal")
            else:
                valor_txt = f"{int(r['Escolas'])} / {compacto_br(r['Funcionarios'])}"
                mini_card(cols[i], titulo, valor_txt, icon="🏫", accent="teal")

        _cards_dependencia(educacao_filtrada, educacao_atingida_gdf, mostrar_educacao_atingida)

    # ---- Lista de Escolas Atingidas (como ruas/imóveis) ----
    if mostrar_educacao_atingida and (educacao_atingida_gdf is not None) and (not educacao_atingida_gdf.empty):
        with st.expander("📋 Escolas Atingidas (lista)", expanded=False):
            tmp = educacao_atingida_gdf.copy()

            # Calcula matrículas por nível por escola para exibição
            def _row_sum_safe(row, cols):
                s = 0.0
                for c in cols:
                    if c in row:
                        v = pd.to_numeric(row[c], errors="coerce")
                        if pd.notna(v):
                            s += float(v)
                return int(s)

            tmp["INFANTIL"]   = tmp.apply(lambda r: _row_sum_safe(r, COLS_INFANTIL), axis=1)
            tmp["FUNDAMENTAL"]= tmp.apply(lambda r: _row_sum_safe(r, COLS_FUNDAMENTAL), axis=1)
            tmp["MEDIO"]      = tmp.apply(lambda r: _row_sum_safe(r, COLS_MEDIO), axis=1)
            if "QT_MAT_PROF" in tmp.columns:
                tmp["TECNICO_PROF"] = pd.to_numeric(tmp["QT_MAT_PROF"], errors="coerce").fillna(0).astype(int)
            else:
                tmp["TECNICO_PROF"] = 0

        # Garante dependência e funcionários (88888 já tratado no carregamento)
            if "DEP_LABEL" not in tmp.columns and "TP_DEPENDENCIA" in tmp.columns:
                tmp["DEP_LABEL"] = tmp["TP_DEPENDENCIA"].apply(dep_label)
            if "QT_FUNCIONARIOS" not in tmp.columns:
            # contingência: soma no ato (tratando 88888 -> 0) se coluna não existir
                def _staff_sum_row(r):
                    total = 0
                    for c in STAFF_COLS:
                        v = pd.to_numeric(r.get(c, 0), errors="coerce")
                        if pd.isna(v) or v == 88888:
                            v = 0
                        total += float(v)
                    return int(total)
                tmp["QT_FUNCIONARIOS"] = tmp.apply(_staff_sum_row, axis=1)

            vis_cols = []
            alias = []
            for col, al in [
                ("NO_ENTIDADE", "Escola"),
                ("DEP_LABEL", "Dependência"),
                ("QT_FUNCIONARIOS", "Funcionários"),
                ("INFANTIL", "Matríc. Infantil"),
                ("FUNDAMENTAL", "Matríc. Fundamental"),
                ("MEDIO", "Matríc. Médio"),
                ("TECNICO_PROF", "Matríc. Técnico/Prof.")
            ]:
                if col in tmp.columns:
                    vis_cols.append(col); alias.append(al)

        # Ordena por maior impacto (ex.: maior total de matrículas atingidas) e nome
            if {"INFANTIL","FUNDAMENTAL","MEDIO","TECNICO_PROF"}.issubset(set(tmp.columns)):
                tmp["_MAT_TOTAL_NIVEIS"] = tmp["INFANTIL"] + tmp["FUNDAMENTAL"] + tmp["MEDIO"] + tmp["TECNICO_PROF"]
                tmp = tmp.sort_values(["_MAT_TOTAL_NIVEIS","NO_ENTIDADE"], ascending=[False, True])
            else:
                tmp = tmp.sort_values(["NO_ENTIDADE"])

            st.dataframe(
                tmp[vis_cols].rename(columns=dict(zip(vis_cols, alias))),
                use_container_width=True, hide_index=True
            )
    # ---------- PRÉDIOS PÚBLICOS & SEGURANÇA ----------
    st.markdown('<div class="painel-sec-titulo">Prédios Públicos e Segurança</div>', unsafe_allow_html=True)
    total_predios   = len(predios_filtrados) if predios_filtrados is not None else 0
    predios_ating   = len(predios_atingidos_gdf) if (modo_atingidos and predios_atingidos_gdf is not None) else 0
    perc_predios    = (predios_ating / total_predios * 100) if total_predios > 0 else 0

    total_seguranca = len(seguranca_filtrada) if seguranca_filtrada is not None else 0
    seguranca_ating = len(seguranca_atingida_gdf) if (modo_atingidos and seguranca_atingida_gdf is not None) else 0
    perc_seguranca  = (seguranca_ating / total_seguranca * 100) if total_seguranca > 0 else 0

    ps1, ps2 = st.columns(2)
    if mostrar_predios_atingidos:
        mini_card(ps1, "Prédios Públicos Atingidos", compacto_br(predios_ating),
                  f"de {compacto_br(total_predios)} ({pct_int(perc_predios)})", icon="🏛️", accent="teal")
    else:
        mini_card(ps1, "Prédios Públicos (Total)", compacto_br(total_predios), icon="🏛️", accent="teal")

    if mostrar_seguranca_atingida:
        mini_card(ps2, "Unidades de Segurança Atingidas", compacto_br(seguranca_ating),
                  f"de {compacto_br(total_seguranca)} ({pct_int(perc_seguranca)})", icon="🛡️", accent="gray")
    else:
        mini_card(ps2, "Unidades de Segurança (Total)", compacto_br(total_seguranca), icon="🛡️", accent="gray")

    # ---------- RUAS ----------
    st.markdown('<div class="painel-sec-titulo">Ruas</div>', unsafe_allow_html=True)
    total_segmentos = len(logradouros_gdf) if logradouros_gdf is not None else 0
    total_ruas_unicas_calc = (logradouros_gdf['_rua_id_interno'].nunique()
                              if (logradouros_gdf is not None and '_rua_id_interno' in logradouros_gdf.columns)
                              else total_segmentos)
    if modo_atingidos and (logradouros_atingidos_gdf is not None):
        seg_ating = len(logradouros_atingidos_gdf)
        ruas_ating = (logradouros_atingidos_gdf['_rua_id_interno'].nunique()
                      if '_rua_id_interno' in logradouros_atingidos_gdf.columns else 0)
    else:
        seg_ating, ruas_ating = 0, 0
    perc_seg = (seg_ating / total_segmentos * 100) if total_segmentos > 0 else 0
    perc_rua = (ruas_ating / total_ruas_unicas_calc * 100) if total_ruas_unicas_calc > 0 else 0

    dren_total = _count_flag01(logradouros_gdf, "drenagem")
    ilum_total = _count_flag01(logradouros_gdf, "iluminacao")
    if mostrar_ruas_atingidas and (logradouros_atingidos_gdf is not None):
        dren_ating = _count_flag01(logradouros_atingidos_gdf, "drenagem")
        ilum_ating = _count_flag01(logradouros_atingidos_gdf, "iluminacao")
    else:
        dren_ating = 0
        ilum_ating = 0
    p_dren = (dren_ating / dren_total * 100) if dren_total > 0 else 0
    p_ilum = (ilum_ating / ilum_total * 100) if ilum_total > 0 else 0

    i1, i2, i3, i4 = st.columns(4)
    if mostrar_ruas_atingidas:
        mini_card(i1, "Segmentos de Rua Atingidos", compacto_br(seg_ating),
                  f"de {compacto_br(total_segmentos)} ({pct_int(perc_seg)})", icon="🛣️", accent="orange")
        mini_card(i2, "Ruas Únicas Atingidas", compacto_br(ruas_ating),
                  f"de {compacto_br(total_ruas_unicas_calc)} ({pct_int(perc_rua)})", icon="📍", accent="orange")
        mini_card(i3, "Drenagem (Atingidos)", compacto_br(dren_ating),
                  f"de {compacto_br(dren_total)} ({pct_int(p_dren)})", icon="🛠️", accent="orange")
        mini_card(i4, "Iluminação (Atingidos)", compacto_br(ilum_ating),
                  f"de {compacto_br(ilum_total)} ({pct_int(p_ilum)})", icon="💡", accent="orange")
    else:
        mini_card(i1, "Segmentos de Rua (Total)", compacto_br(total_segmentos), icon="🛣️", accent="orange")
        mini_card(i2, "Ruas Únicas (Total)", compacto_br(total_ruas_unicas_calc), icon="📍", accent="orange")
        mini_card(i3, "Drenagem (Total)", compacto_br(dren_total), icon="🛠️", accent="orange")
        mini_card(i4, "Iluminação (Total)", compacto_br(ilum_total), icon="💡", accent="orange")

    if mostrar_ruas_atingidas and (logradouros_atingidos_gdf is not None) and (not logradouros_atingidos_gdf.empty):
        with st.expander("📋 Lista de Ruas Atingidas", expanded=False):
            tmp = logradouros_atingidos_gdf.copy()
            if 'tipo' not in tmp.columns: tmp['tipo'] = ''
            if 'nome' not in tmp.columns: tmp['nome'] = tmp.get('_rua_id_interno', tmp.index.astype(str))
            if '_rua_id_interno' not in tmp.columns:
                tmp['_rua_id_interno'] = (tmp['tipo'].astype(str).str.strip() + ' ' + tmp['nome'].astype(str).str.strip()).str.strip()
            df_ruas = (
                tmp.groupby(['_rua_id_interno','tipo','nome'], dropna=False)
                .size().reset_index(name='Segmentos Atingidos')
                .sort_values(['Segmentos Atingidos','tipo','nome'], ascending=[False, True, True])
                .reset_index(drop=True)
            )
            st.dataframe(
                df_ruas[['tipo','nome','Segmentos Atingidos']].rename(
                    columns={'tipo': 'Tipo','nome': 'Nome da Rua','Segmentos Atingidos': '# Segmentos Atingidos'}
                ),
                use_container_width=True, hide_index=True
            )

    # ---------- TERRENOS & QUADRAS ----------
    st.markdown('<div class="painel-sec-titulo">Terrenos e Quadras</div>', unsafe_allow_html=True)
    tq1, tq2, tq3, tq4 = st.columns(4)
    terr_ating = len(terrenos_atingidos_gdf) if (modo_atingidos and terrenos_atingidos_gdf is not None) else 0
    quad_ating = len(quadras_atingidas_gdf)  if (modo_atingidos and quadras_atingidas_gdf  is not None) else 0
    perc_terr = (terr_ating / total_terrenos * 100) if total_terrenos > 0 else 0
    perc_quad = (quad_ating / total_quadras  * 100) if total_quadras  > 0 else 0

    if mostrar_terrenos_atingidos:
        mini_card(tq1, "Terrenos Atingidos", compacto_br(terr_ating),
                  f"de {compacto_br(total_terrenos)} ({pct_int(perc_terr)})", icon="🧱", accent="green")
        mini_card(tq2, "Quadras Atingidas", compacto_br(quad_ating),
                  f"de {compacto_br(total_quadras)} ({pct_int(perc_quad)})", icon="🧩", accent="purple")
    else:
        mini_card(tq1, "Terrenos (Total)", compacto_br(total_terrenos), icon="🧱", accent="green")
        mini_card(tq2, "Quadras (Total)", compacto_br(total_quadras), icon="🧩", accent="purple")
    tq3.write(""); tq4.write("")

    # ----- Serviços nos Terrenos -----
    agua_total    = _count_flag01(terrenos_gdf, "agua")
    lixo_total    = _count_flag01(terrenos_gdf, "coleta_lix")
    pluvial_total = _count_flag01(terrenos_gdf, "esgoto_plu")
    condo_total   = _count_flag01(terrenos_gdf, "condominio")
    cloacal_total = _count_equals(terrenos_gdf, "esgoto_clo", values={"esgoto_cloacal"})
    fossa_total   = _count_equals(terrenos_gdf, "esgoto_clo", values={"fossa_septica"})

    if mostrar_terrenos_atingidos and (terrenos_atingidos_gdf is not None):
        agua_ating    = _count_flag01(terrenos_atingidos_gdf, "agua")
        lixo_ating    = _count_flag01(terrenos_atingidos_gdf, "coleta_lix")
        pluvial_ating = _count_flag01(terrenos_atingidos_gdf, "esgoto_plu")
        condo_ating   = _count_flag01(terrenos_atingidos_gdf, "condominio")
        cloacal_ating = _count_equals(terrenos_atingidos_gdf, "esgoto_clo", values={"esgoto_cloacal"})
        fossa_ating   = _count_equals(terrenos_atingidos_gdf, "esgoto_clo", values={"fossa_septica"})
    else:
        agua_ating = lixo_ating = pluvial_ating = condo_ating = cloacal_ating = fossa_ating = 0

    p_agua    = (agua_ating    / agua_total * 100)    if agua_total    > 0 else 0
    p_lixo    = (lixo_ating    / lixo_total * 100)    if lixo_total    > 0 else 0
    p_pluvial = (pluvial_ating / pluvial_total * 100) if pluvial_total > 0 else 0
    p_condo   = (condo_ating   / condo_total * 100)   if condo_total   > 0 else 0
    p_cloacal = (cloacal_ating / cloacal_total * 100) if cloacal_total > 0 else 0
    p_fossa   = (fossa_ating   / fossa_total * 100)   if fossa_total   > 0 else 0

    s1, s2, s3 = st.columns(3)
    s4, s5, s6 = st.columns(3)
    if mostrar_terrenos_atingidos:
        mini_card(s1, "Água (Atingidos)", compacto_br(agua_ating),
                  f"de {compacto_br(agua_total)} ({pct_int(p_agua)})", icon="🚰", accent="green")
        mini_card(s2, "Coleta de Lixo (Atingidos)", compacto_br(lixo_ating),
                  f"de {compacto_br(lixo_total)} ({pct_int(p_lixo)})", icon="🗑️", accent="green")
        mini_card(s3, "Esgoto Pluvial (Atingidos)", compacto_br(pluvial_ating),
                  f"de {compacto_br(pluvial_total)} ({pct_int(p_pluvial)})", icon="💧", accent="green")
        mini_card(s4, "Esgoto Cloacal (Atingidos)", compacto_br(cloacal_ating),
                  f"de {compacto_br(cloacal_total)} ({pct_int(p_cloacal)})", icon="🪠", accent="green")
        mini_card(s5, "Fossa Séptica (Atingidos)", compacto_br(fossa_ating),
                  f"de {compacto_br(fossa_total)} ({pct_int(p_fossa)})", icon="🕳️", accent="green")
        mini_card(s6, "Condomínios (Atingidos)", compacto_br(condo_ating),
                  f"de {compacto_br(condo_total)} ({pct_int(p_condo)})", icon="🏢", accent="green")
    else:
        mini_card(s1, "Água (Total)", compacto_br(agua_total), icon="🚰", accent="green")
        mini_card(s2, "Coleta de Lixo (Total)", compacto_br(lixo_total), icon="🗑️", accent="green")
        mini_card(s3, "Esgoto Pluvial (Total)", compacto_br(pluvial_total), icon="💧", accent="green")
        mini_card(s4, "Esgoto Cloacal (Total)", compacto_br(cloacal_total), icon="🪠", accent="green")
        mini_card(s5, "Fossa Séptica (Total)", compacto_br(fossa_total), icon="🕳️", accent="green")
        mini_card(s6, "Condomínios (Total)", compacto_br(condo_total), icon="🏢", accent="green")

    # ---------- IMÓVEIS ----------
    st.markdown('<div class="painel-sec-titulo">Imóveis</div>', unsafe_allow_html=True)

    def _cond1_count(gdf):
        if gdf is None or len(gdf) == 0: return 0
        s = pd.to_numeric(gdf.get('Condom', 0), errors='coerce').fillna(0).astype(int)
        return int((s == 1).sum())

    imoveis_ating = len(imoveis_atingidos_gdf) if (modo_atingidos and imoveis_atingidos_gdf is not None) else 0
    cond1_total   = _cond1_count(_to_point_gdf(imoveis_gdf)) if imoveis_gdf is not None else 0
    cond1_ating   = _cond1_count(imoveis_atingidos_gdf) if (modo_atingidos and imoveis_atingidos_gdf is not None) else 0
    p_imoveis     = (imoveis_ating / total_imoveis * 100) if total_imoveis > 0 else 0
    p_cond1       = (cond1_ating / cond1_total * 100) if cond1_total > 0 else 0

    ci1, ci2 = st.columns(2)
    if mostrar_imoveis_atingidos:
        mini_card(ci1, "Imóveis Atingidos", compacto_br(imoveis_ating),
                  f"de {compacto_br(total_imoveis)} ({pct_int(p_imoveis)})", icon="🏠", accent="purple")
        mini_card(ci2, "Condomínios", compacto_br(cond1_ating),
                  f"de {compacto_br(cond1_total)} ({pct_int(p_cond1)})", icon="🏢", accent="purple")
    else:
        mini_card(ci1, "Imóveis (Total)", compacto_br(total_imoveis), icon="🏠", accent="purple")
        mini_card(ci2, "Condomínios", compacto_br(cond1_total), icon="🏢", accent="purple")

    def _counts_dict(gdf, col):
        if gdf is None or len(gdf) == 0 or (col not in gdf.columns): return {}
        s_raw = gdf[col].astype(str).str.strip()
        s_norm = s_raw.str.lower()
        outros_tokens = {"", "none", "nan", "na", "null", "sem informação", "sem informacao", "outro", "outros"}
        mask_outros = s_norm.isin(outros_tokens)
        labels = {}
        for raw, n in zip(s_raw[~mask_outros], s_norm[~mask_outros]):
            if n not in labels and raw != "": labels[n] = raw
        counts = s_norm[~mask_outros].value_counts().to_dict()
        out = {labels[k]: int(v) for k, v in counts.items() if k in labels}
        outros_count = int(mask_outros.sum())
        if outros_count > 0: out["Outros"] = out.get("Outros", 0) + outros_count
        return out

    def _render_table_expander(titulo, total_dict, ating_dict=None):
        labels = sorted(total_dict.keys(), key=lambda k: (-total_dict[k], k))
        rows = []
        for lb in labels:
            tot = int(total_dict.get(lb, 0))
            if (ating_dict is not None) and modo_atingidos:
                atg = int(ating_dict.get(lb, 0))
                perc = (atg / tot * 100) if tot else 0
                rows.append([lb, tot, atg, f"{perc:.1f}%"])
            else:
                rows.append([lb, tot])
        if (ating_dict is not None) and modo_atingidos:
            df = pd.DataFrame(rows, columns=["Categoria", "Total", "Atingidos", "% atingidos"])
        else:
            df = pd.DataFrame(rows, columns=["Categoria", "Total"])
        with st.expander(titulo, expanded=False):
            st.dataframe(df, use_container_width=True, hide_index=True)

    uso_total    = _counts_dict(_to_point_gdf(imoveis_gdf), "Uso") if imoveis_gdf is not None else {}
    uso_ating    = _counts_dict(imoveis_atingidos_gdf, "Uso") if (modo_atingidos and imoveis_atingidos_gdf is not None) else None
    patrim_total = _counts_dict(_to_point_gdf(imoveis_gdf), "Patrim") if imoveis_gdf is not None else {}
    patrim_ating = _counts_dict(imoveis_atingidos_gdf, "Patrim") if (modo_atingidos and imoveis_atingidos_gdf is not None) else None

    _render_table_expander("Imóveis por Tipo de Uso", uso_total, uso_ating)
    _render_table_expander("Imóveis por Patrimônio", patrim_total, patrim_ating)

# ========= Mapa =========
st.subheader("Mapa Interativo")

def _latlon_from_row(row):
    if hasattr(row, "geometry") and row.geometry is not None:
        try:
            x = getattr(row.geometry, "x", None)
            y = getattr(row.geometry, "y", None)
            if (x is not None) and (y is not None):
                return (float(y), float(x))
        except Exception:
            pass
    lat = row.get("latitude", None); lon = row.get("longitude", None)
    if (lat is not None) and (lon is not None):
        return (float(lat), float(lon))
    lat = row.get("Latitude", None); lon = row.get("Longitude", None)
    if (lat is not None) and (lon is not None):
        try:
            return (float(lat), float(lon))
        except Exception:
            return None
    return None

def _cluster(color_hex):
    return MarkerCluster(
        name="",
        icon_create_function=f"""
        function (cluster) {{
          var count = cluster.getChildCount();
          return L.divIcon({{
            html: '<div style="background:{color_hex}; color:#fff; width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700;">'+count+'</div>',
            className: 'custom-cluster',
            iconSize: new L.Point(40, 40)
          }});
        }}
        """
    )

with st.spinner("Atualizando mapa..."):
    m = folium.Map(location=[-32.0540, -52.1150], zoom_start=13, tiles="CartoDB positron")

    if mancha_selecionada_gdf is not None:
        folium.GeoJson(
            mancha_selecionada_gdf,
            name=selecao_mancha_nome,
            show=True,
            tooltip=selecao_mancha_nome,
            style_function=lambda x: {'color': 'blue', 'weight': 1.5, 'fillColor': '#3186cc', 'fillOpacity': 0.6}
        ).add_to(m)

    # Empresas
    empresas_para_plotar = (
        empresas_atingidas_gdf if mostrar_empresas_atingidas else empresas_filtradas
    )
    if mostrar_empresas and (empresas_para_plotar is not None) and (not empresas_para_plotar.empty):
        fg_empresas = folium.FeatureGroup(name="Empresas", show=True)
        mc_emp = _cluster("#1976d2").add_to(fg_empresas)
        icon_emp = get_custom_icon("Empresas", size=(28,28))
        for _, row in empresas_para_plotar.iterrows():
            ll = _latlon_from_row(row)
            if ll is None:
                continue
            massa_salarial_pop = formatar_br(row.get('Massa_Salarial', 0))
            media_salarial_pop = formatar_br(row.get('MédiaSalarial', 0))
            popup_html = (
                f"<b>ID:</b> {row.get('id', 'N/A')}<br>"
                f"<b>Empregados:</b> {row.get('Empregados', 'N/A')}<br>"
                f"<b>Massa Salarial:</b> R$ {massa_salarial_pop}<br>"
                f"<b>Média Salarial:</b> R$ {media_salarial_pop}"
            )
            folium.Marker(location=ll, popup=folium.Popup(popup_html, max_width=300), icon=icon_emp).add_to(mc_emp)
        fg_empresas.add_to(m)

    # Saúde
    saude_para_plotar = (
        saude_atingida_gdf if mostrar_saude_atingida else saude_filtrada
    )
    if mostrar_saude and (saude_para_plotar is not None) and (not saude_para_plotar.empty):
        fg_saude = folium.FeatureGroup(name="Saúde", show=True)
        mc_saude = _cluster("#2e7d32").add_to(fg_saude)
        icon_sau = get_custom_icon("Saude", size=(28,28))
        for _, row in saude_para_plotar.iterrows():
            ll = _latlon_from_row(row)
            if ll is None:
                try:
                    geom = row.geometry
                    ll = (float(geom.y), float(geom.x))
                except Exception:
                    continue
            nome  = row.get('NO_FANTASIA', 'Sem Nome')
            bairro = row.get('NO_BAIRRO', '—')
            lograd = row.get('NO_LOGRADOURO', '—')
            numero = row.get('NU_ENDERECO', '—')
            popup_html = (f"<b>Nome:</b> {nome}<br><b>Bairro:</b> {bairro}<br><b>Logradouro:</b> {lograd}<br><b>Número:</b> {numero}")
            folium.Marker(location=ll, popup=folium.Popup(popup_html, max_width=320), icon=icon_sau).add_to(mc_saude)
        fg_saude.add_to(m)

    # Educação (FIX: sem fallback quando "Atingidos" estiver marcado)
    educacao_para_plotar = (
        educacao_atingida_gdf if mostrar_educacao_atingida else educacao_filtrada
    )

    if mostrar_educacao and (educacao_para_plotar is not None) and (not educacao_para_plotar.empty):
        fg_edu = folium.FeatureGroup(name="Educação", show=True)
        mc_edu = _cluster("#0d9488").add_to(fg_edu)  # teal
        icon_edu = get_custom_icon("Escola", size=(28,28))

        for _, row in educacao_para_plotar.iterrows():
            ll = _latlon_from_row(row)
            if ll is None:
                continue

        # ---------- Funcionários no POPUP (robusto ao 88888) ----------
            staff_sum = 0
            for c in STAFF_COLS:  # STAFF_COLS já definido na seção EDUCAÇÃO
                v = pd.to_numeric(row.get(c, 0), errors="coerce")
                if pd.isna(v) or v == 88888:
                    v = 0
                staff_sum += float(v)
            func = int(staff_sum)

        # ---------- Demais campos ----------
            nome = row.get("NO_ENTIDADE", "Sem Nome")
            dep  = row.get("DEP_LABEL", dep_label(row.get("TP_DEPENDENCIA", "")))

            mb = pd.to_numeric(row.get("QT_MAT_BAS", 0), errors="coerce")
            mp = pd.to_numeric(row.get("QT_MAT_PROF", 0), errors="coerce")
            mat_total = int((0 if pd.isna(mb) else mb) + (0 if pd.isna(mp) else mp))

        # ---------- Popup ----------
            popup_html = (
                f"<b>Escola:</b> {nome}<br>"
                f"<b>Dependência:</b> {dep}<br>"
                f"<b>Funcionários:</b> {func}<br>"
                f"<b>Matrículas (Básica + Prof.):</b> {mat_total}"
            )

            folium.Marker(
                location=ll,
                popup=folium.Popup(popup_html, max_width=360),
                icon=icon_edu
            ).add_to(mc_edu)

        fg_edu.add_to(m)

    # Ruas
    if mostrar_ruas_atingidas and (logradouros_atingidos_gdf is not None) and (not logradouros_atingidos_gdf.empty):
        folium.GeoJson(
            logradouros_atingidos_gdf, name="Logradouros Atingidos", show=True,
            tooltip=folium.features.GeoJsonTooltip(
                fields=[f for f in ['tipo','nome'] if f in logradouros_atingidos_gdf.columns],
                aliases=['Tipo:', 'Nome:']
            ),
            style_function=lambda x: {'color': 'red', 'weight': 4}
        ).add_to(m)

    # Terrenos
    if mostrar_terrenos_atingidos and (terrenos_atingidos_gdf is not None) and (not terrenos_atingidos_gdf.empty):
        folium.GeoJson(
            terrenos_atingidos_gdf, name="Terrenos Atingidos", show=True,
            tooltip=folium.features.GeoJsonTooltip(
                fields=[f for f in ['area_lote'] if f in terrenos_atingidos_gdf.columns],
                aliases=['Área do Lote (m²):']
            ),
            style_function=lambda x: {'color': '#b34700', 'weight': 1, 'fillColor': '#ff7f00', 'fillOpacity': 0.45}
        ).add_to(m)

    # Quadras
    if mostrar_quadras_atingidas and (quadras_atingidas_gdf is not None) and (not quadras_atingidas_gdf.empty):
        quad_fields = [c for c in ['id','area','area_m2'] if c in quadras_atingidas_gdf.columns]
        aliases = ['ID:', 'Área:', 'Área (m²):'][:len(quad_fields)]
        folium.GeoJson(
            quadras_atingidas_gdf, name="Quadras Atingidas", show=True,
            tooltip=folium.features.GeoJsonTooltip(fields=quad_fields, aliases=aliases) if quad_fields else None,
            style_function=lambda x: {'color': '#6f42c1', 'weight': 1, 'fillColor': '#b197fc', 'fillOpacity': 0.35}
        ).add_to(m)

    # Imóveis (somente atingidos)
    if mostrar_imoveis_atingidos and (imoveis_atingidos_gdf is not None) and (not imoveis_atingidos_gdf.empty):
        fg_imoveis = folium.FeatureGroup(name="Imóveis Atingidos", show=True)
        mc_imov = _cluster("#6f42c1").add_to(fg_imoveis)
        icon_imv = get_custom_icon("PrediosPublicos", size=(24,24))
        for _, row in imoveis_atingidos_gdf.iterrows():
            geom = row.geometry
            ll = (float(geom.y), float(geom.x))
            linhas = []
            if "Uso" in imoveis_atingidos_gdf.columns:    linhas.append(f"<b>Uso:</b> {row.get('Uso')}")
            if "Patrim" in imoveis_atingidos_gdf.columns: linhas.append(f"<b>Patrim:</b> {row.get('Patrim')}")
            if "Condom" in imoveis_atingidos_gdf.columns: linhas.append(f"<b>Condomínio:</b> {row.get('Condom')}")
            pop = folium.Popup("<br>".join(linhas), max_width=260) if linhas else None
            folium.Marker(location=ll, popup=pop, icon=icon_imv).add_to(mc_imov)
        fg_imoveis.add_to(m)

    # Prédios Públicos
    predios_para_plotar = (
        predios_atingidos_gdf if mostrar_predios_atingidos else predios_filtrados
    )
    if mostrar_predios and (predios_para_plotar is not None) and (len(predios_para_plotar) > 0):
        fg_pp = folium.FeatureGroup(name="Prédios Públicos", show=True)
        mc_pp = _cluster("#00695c").add_to(fg_pp)
        for _, row in predios_para_plotar.iterrows():
            ll = _latlon_from_row(row)
            if ll is None: 
                continue
            nome  = row.get('Nome', 'Sem Nome')
            ender = row.get('Endereço', '—') if 'Endereço' in predios_para_plotar.columns else row.get('Endereco', '—')
            popup_html = (f"<b>Nome:</b> {nome}<br><b>Endereço:</b> {ender}")
            tipo_val = str(row.get('Tipo', '')).lower()
            use_escola = ("escola" in tipo_val) or ("educa" in tipo_val)
            icon_pp = get_custom_icon("Escola", size=(28,28)) if use_escola else get_custom_icon("PrediosPublicos", size=(28,28))
            folium.Marker(location=ll, popup=folium.Popup(popup_html, max_width=320), icon=icon_pp).add_to(mc_pp)
        fg_pp.add_to(m)

    # Segurança
    seguranca_para_plotar = (
        seguranca_atingida_gdf if mostrar_seguranca_atingida else seguranca_filtrada
    )
    if mostrar_seguranca and (seguranca_para_plotar is not None) and (len(seguranca_para_plotar) > 0):
        fg_sg = folium.FeatureGroup(name="Segurança", show=True)
        mc_sg = _cluster("#424242").add_to(fg_sg)
        icon_seg = get_custom_icon("Seguranca", size=(28,28))
        for _, row in seguranca_para_plotar.iterrows():
            ll = _latlon_from_row(row)
            if ll is None:
                continue
            nome  = row.get('Nome', 'Sem Nome')
            ender = row.get('Endereço', '—') if 'Endereço' in seguranca_para_plotar.columns else row.get('Endereco', '—')
            popup_html = (f"<b>Nome:</b> {nome}<br><b>Endereço:</b> {ender}")
            folium.Marker(location=ll, popup=folium.Popup(popup_html, max_width=320), icon=icon_seg).add_to(mc_sg)
        fg_sg.add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    st_folium(m, width="100%", height=600, returned_objects=[])

# ---------- Rodapé ----------
st.markdown("""
<div class="footer-bar">
  © 2025 Grupo de Pesquisa em Economia Aplicada, Universidade Federal de Rio Grande - FURG |
  Desenvolvido por <strong>Alisson Tallys Geraldo Fiorentin</strong>
</div>
""", unsafe_allow_html=True)
