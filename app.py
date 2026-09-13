import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from openai import OpenAI
from difflib import SequenceMatcher

# ========== 将上传组件英文字符隐藏 ==========
# ========== 将上传组件英文字符隐藏 ==========
st.markdown("""
    <style>
    /* 1. 把整个白框撑大，让内容有足够空间 */
    [data-testid="stFileUploaderDropzone"] {
        padding: 50px 30px !important; 
        min-height: 180px !important; 
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
    }

    /* 2. 第一行提示文字 */
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
        visibility: hidden; position: relative;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span::after {
        content: "拖拽文件到这里，或点击下方按钮";
        visibility: visible; position: absolute; 
        left: 0; top: 0; white-space: nowrap;
        font-size: 15px; /* 稍微调大字体 */
    }

    /* 3. 第二行格式限制文字 */
    [data-testid="stFileUploaderDropzoneInstructions"] > div > small {
        visibility: hidden; position: relative;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > small::after {
        content: "单个文件不超过 200MB，支持 XLSX 格式";
        visibility: visible; position: absolute; 
        left: 0; top: 25px; white-space: nowrap;
        font-size: 13px;
    }

    /* 4. 按钮本体：隐藏原本的英文文字，留出空间 */
    /* 4. 按钮本体：隐藏原本的英文文字 */
[data-testid="stFileUploaderDropzone"] button {
    color: transparent !important;
    position: relative !important;
    min-width: 130px !important;
    margin-top: 25px !important;
    border: 1px solid #CCCCCC !important;
    background-color: #F9F9F9 !important;
    /*  新增：强制按钮内容靠左，加一点内边距 */
    justify-content: flex-start !important;
    padding-left: 25px !important;
}

/* 5. 按钮上的中文文字 */
[data-testid="stFileUploaderDropzone"] button::after {
    content: "选择文件";
    position: absolute;
    /*  把居中去掉，改成靠左定位 */
    left: 25px;
    top: 50%;
    transform: translateY(-50%);  /* 只做垂直居中 */
    color: #333333;
    font-weight: 600;
    font-size: 15px;
    white-space: nowrap;
}
    </style>
""", unsafe_allow_html=True)


st.markdown("""
    <style>
    .custom-title h1 {
        font-size: 36px !important;    /* 第一行字号 */
        margin-bottom: 0px !important;
        text-align: left;              /* 靠左对齐 */
    }
    .custom-title h2 {
        font-size: 32px !important;    /* 第二行字号 */
        margin-top: -12px !important;
        text-align: left;              /* 靠左对齐 */
    }
    </style>
    <div class="custom-title">
        <h1>智葛助农：</h1>
        <h2>竹山粉葛知识问答系统</h2>
    </div>
""", unsafe_allow_html=True)

# ========== 配置区 ==========
DB_URL = st.secrets["database"]["url"]
ZHIPU_API_KEY = st.secrets["zhipu_api_key"]

client = OpenAI(
    api_key=ZHIPU_API_KEY,
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

# ========== 初始化 session_state（记忆参数） ==========
if 'similarity_threshold' not in st.session_state:
    st.session_state.similarity_threshold = 0.75
if 'use_ai' not in st.session_state:
    st.session_state.use_ai = False  # ← 改成 False，默认不开启 AI

# ========== 数据加载 ==========
@st.cache_data
def load_data():
    engine = create_engine(DB_URL)
    return pd.read_sql('SELECT * FROM excel_data', con=engine)

df = load_data()

# ========== 相似度函数 ==========
def calculate_similarity(a, b):
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()

# ========== 侧边栏：折叠式管理面板 ==========
with st.sidebar:
    st.header("⚙️ 系统设置")

    with st.expander("📁 数据管理（点击展开）"):
        uploaded_file = st.file_uploader("上传新的 Excel 文件", type=['xlsx'])
        if uploaded_file is not None:
            if st.button("开始更新数据库"):
                try:
                    df_new = pd.read_excel(uploaded_file)
                    engine = create_engine(DB_URL)
                    df_new.to_sql('excel_data', con=engine, if_exists='replace', index=False)
                    st.success("✅ 数据库更新成功！")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f" 更新失败：{e}")

    with st.expander("🎛️ 问答参数（点击展开）"):
        st.session_state.similarity_threshold = st.slider(
            "相似度阈值（大于此值才显示数据库答案）",
            0.5, 1.0,
            value=st.session_state.similarity_threshold,
            step=0.05
        )
        st.session_state.use_ai = st.checkbox(
            "数据库搜不到时，让 粉葛AI 补充回答",
            value=st.session_state.use_ai
        )

# 从 session_state 里取出参数
similarity_threshold = st.session_state.similarity_threshold
use_ai = st.session_state.use_ai

# ========== 主问答逻辑 ==========
# 输入框 + 搜索按钮（左右布局）
col1, col2 = st.columns([5, 1])  # 输入框占5份宽度，按钮占1份

with col1:
    user_input = st.text_input("请输入您的问题：", label_visibility="collapsed")

with col2:
    st.write("")  # 占位，让按钮和输入框对齐
    search_clicked = st.button(" 搜索", use_container_width=True)

# 只有当用户点击了“搜索”按钮，且输入框非空时，才执行查询
if search_clicked and user_input:
    # 下面接着写你原来的查询逻辑
    df['相似度'] = df['问题'].apply(lambda q: calculate_similarity(user_input, q))
    result = df[df['相似度'] > similarity_threshold].sort_values('相似度', ascending=False)

    if not result.empty:
        st.success(f"📚 在数据库中找到 {len(result)} 条相关答案：")
        for index, row in result.iterrows():
            st.write(f"**分类**：{row['分类']}")
            st.write(f"**问题**：{row['问题']}")
            st.info(f"**答案**：{row['答案']}")
            st.caption(f"相似度：{row['相似度']:.2%}")
    else:
        if use_ai:
            st.warning("📚 数据库中没有找到相似度足够高的问题，正在调用 AI 回答...")
            with st.spinner("AI 正在思考中..."):
                try:
                    prompt = f"你是粉葛领域的专家，请回答用户的问题。如果问题涉及专业术语或历史背景，请详细说明。\n\n用户问题：{user_input}"
                    response = client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": prompt}],
                    )
                    st.success("🤖 AI 补充回答：")
                    st.write(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"AI 调用失败：{e}")
        else:
            st.warning("抱歉，数据库中没有找到相似度足够高的答案。")

if user_input:
    df['相似度'] = df['问题'].apply(lambda q: calculate_similarity(user_input, q))
    result = df[df['相似度'] > similarity_threshold].sort_values('相似度', ascending=False)

    if not result.empty:
        st.success(f"📚 在数据库中找到 {len(result)} 条相关答案：")
        for index, row in result.iterrows():
            st.write(f"**分类**：{row['分类']}")
            st.write(f"**问题**：{row['问题']}")
            st.info(f"**答案**：{row['答案']}")
            st.caption(f"相似度：{row['相似度']:.2%}")
    else:
        if use_ai:
            st.warning("📚 数据库中没有找到相似度足够高的问题，正在调用 粉葛AI 回答...")
            with st.spinner("AI 正在思考中..."):
                try:
                    prompt = f"你是粉葛领域的专家，请回答用户的问题。如果问题涉及专业术语或历史背景，请详细说明。\n\n用户问题：{user_input}"
                    response = client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": prompt}],
                    )
                    st.success("🤖 AI 补充回答：")
                    st.write(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"AI 调用失败：{e}")
        else:
            st.warning("抱歉，数据库中没有找到相似度足够高的答案（粉葛AI 补充功能已关闭）。")
