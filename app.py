import streamlit as st
import json
import requests
import base64
import os
import io
import shutil
from PIL import Image
from streamlit_paste_button import paste_image_button as pbutton

# ==========================================
# 0. 初始化配置与工具函数
# ==========================================

# 确保资源目录存在
ASSETS_DIR = "assets"
if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR)

# --- 核心：后端配置加载 ---
def get_llm_config():
    """从 .streamlit/secrets.toml 加载配置"""
    try:
        if "llm" not in st.secrets:
            st.error("❌ 配置文件错误：未在 secrets.toml 中找到 [llm] 部分。")
            st.stop()
            
        config = st.secrets["llm"]
        
        # 必填项检查
        if not config.get("api_key"):
            st.error("❌ 配置丢失：请在 secrets.toml 中填写 api_key")
            st.stop()
            
        return config["api_key"], config.get("base_url", "https://api.deepseek.com"), config.get("model", "deepseek-chat")
        
    except FileNotFoundError:
        st.error("""
        ❌ 未找到配置文件！
        请在项目根目录下创建文件夹 `.streamlit`，并在其中创建 `secrets.toml` 文件。
        内容格式如下：
        
        [llm]
        api_key = "sk-your-key-here"
        base_url = "https://api.deepseek.com"
        model = "deepseek-chat"
        """)
        st.stop()

# --- 数据加载与保存 ---

def load_ingredients():
    if not os.path.exists('ingredients.json'):
        return {}
    with open('ingredients.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_ingredients(data):
    with open('ingredients.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_recipes():
    if not os.path.exists('recipes.json'):
        return []
    with open('recipes.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_recipes(data):
    with open('recipes.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 图像处理 ---

def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- AI 核心逻辑 ---

def identify_ingredients(api_key, base_url, model_name, base64_image, known_names):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    known_list_str = ", ".join(known_names)
    
    system_prompt = "你是一个游戏识别助手。"
    user_prompt = f"""
    请分析图片。图片中包含了一些游戏食材。
    请识别出它们，并**严格**从以下【已知列表】中选择对应的名字：
    【已知列表】：[{known_list_str}]
    
    规则：
    1. 如果图片里的物体非常像列表里的某样东西，请使用列表里的名字。
    2. 如果图片里的物体完全不在列表里，请忽略它。
    3. 只返回一个 JSON 列表字符串，不要包含 Markdown 格式，例如：['龙虾', '番茄']
    """

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 500
    }
    
    try:
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        response_json = response.json()
        
        if 'error' in response_json:
            st.error(f"API Error: {response_json['error']}")
            return []
            
        content = response_json['choices'][0]['message']['content']
        content = content.replace("```json", "").replace("```", "").strip()
        return eval(content)
    except Exception as e:
        st.error(f"识别错误: {str(e)}")
        return []

# ==========================================
# 1. 界面主逻辑
# ==========================================

st.set_page_config(page_title="suki助手", layout="wide", page_icon="🤖")
st.title("🍙 游戏食材图鉴与配方助手")

# --- 后端配置加载 (自动) ---
API_KEY, BASE_URL, MODEL_NAME = get_llm_config()

# --- 侧边栏 ---
with st.sidebar:
    st.success(f"✅ 系统已就绪\n\n**当前模型**: `{MODEL_NAME}`")
    st.divider()
    st.info("""
    **使用流程：**
    1. **图鉴管理**：录入食材（支持粘贴）。
    2. **配方管理**：配置组合与筛选。
    3. **拍照识别**：上传截图，AI 自动计算。
    """)

# --- 标签页 ---
tab1, tab2, tab3 = st.tabs(["📚 图鉴管理", "⚗️ 配方管理", "📸 拍照识别"])

# ==========================================
# Tab 1: 图鉴管理
# ==========================================
with tab1:
    st.subheader("1. 定义游戏里的食材")
    col_input, col_view = st.columns([1, 2])
    
    all_ingredients = load_ingredients()
    
    with col_input:
        st.info("💡 录入技巧：截图后直接点击下方【粘贴】按钮。")
        new_name = st.text_input("食材名称", placeholder="例如: 饼干")
        
        upload_tab, paste_tab = st.tabs(["📂 文件上传", "📋 剪切板粘贴"])
        image_data_to_save = None 
        
        with upload_tab:
            uploaded_file = st.file_uploader("选择图片文件", type=['png', 'jpg', 'jpeg'], key="uploader")
            if uploaded_file:
                image_data_to_save = uploaded_file.getvalue()
        
        with paste_tab:
            paste_result = pbutton(
                label="📋 点击此处读取剪切板图片",
                text_color="#ffffff",
                background_color="#FF4B4B",
                hover_background_color="#FF0000",
            )
            if paste_result.image_data is not None:
                st.success("已读取剪切板图片！")
                st.image(paste_result.image_data, caption="剪切板预览", width=150)
                img_byte_arr = io.BytesIO()
                paste_result.image_data.save(img_byte_arr, format='PNG')
                image_data_to_save = img_byte_arr.getvalue()

        if st.button("➕ 添加到图鉴", type="primary"):
            if new_name and image_data_to_save:
                if new_name in all_ingredients:
                    st.warning(f"'{new_name}' 已存在，将覆盖旧图。")
                file_name = f"{new_name}.png" 
                file_path = os.path.join(ASSETS_DIR, file_name)
                with open(file_path, "wb") as f:
                    f.write(image_data_to_save)
                all_ingredients[new_name] = file_path
                save_ingredients(all_ingredients)
                st.success(f"✅ 已添加: {new_name}")
                st.rerun()
            else:
                st.error("❌ 请输入名称并上传图片")

    with col_view:
        st.write(f"📦 已有食材库 ({len(all_ingredients)})")
        if all_ingredients:
            cols = st.columns(4)
            for i, (name, img_path) in enumerate(all_ingredients.items()):
                with cols[i % 4]:
                    try:
                        st.image(img_path, width=80)
                        st.caption(name)
                        if st.button("🗑️", key=f"del_{name}"):
                            del all_ingredients[name]
                            if os.path.exists(img_path):
                                try: os.remove(img_path)
                                except: pass
                            save_ingredients(all_ingredients)
                            st.rerun()
                    except:
                        st.error(f"❌ {name}")
        else:
            st.info("暂无食材。")

# ==========================================
# Tab 2: 配方管理 (筛选+排序+去重)
# ==========================================
with tab2:
    st.subheader("2. 配置食材配方")
    current_recipes = load_recipes()
    ingredient_names = list(all_ingredients.keys())
    
    if not ingredient_names:
        st.warning("请先在【图鉴管理】中添加食材！")
    else:
        # 新增表单
        with st.form("add_recipe_form"):
            c1, c2 = st.columns([1, 3])
            with c1:
                r_tier = st.selectbox("产出等级", ["高级", "普通", "黑暗"])
            with c2:
                r_ingredients = st.multiselect("所需食材 (多选)", ingredient_names)
            
            if st.form_submit_button("💾 保存公式"):
                if not r_ingredients:
                    st.error("❌ 至少选一个食材")
                else:
                    new_set = set(r_ingredients)
                    found_index = -1
                    is_exact_duplicate = False
                    for i, recipe in enumerate(current_recipes):
                        if set(recipe['ingredients']) == new_set:
                            found_index = i
                            if recipe['tier'] == r_tier: is_exact_duplicate = True
                            break
                    
                    if is_exact_duplicate:
                        st.warning("⚠️ 配方已存在。")
                    elif found_index != -1:
                        old_tier = current_recipes[found_index]['tier']
                        current_recipes[found_index]['tier'] = r_tier
                        current_recipes[found_index]['ingredients'] = r_ingredients 
                        save_recipes(current_recipes)
                        st.success(f"🔄 配方已更新：{old_tier} -> {r_tier}")
                        st.rerun()
                    else:
                        current_recipes.append({"tier": r_tier, "ingredients": r_ingredients})
                        save_recipes(current_recipes)
                        st.success("✅ 新公式已保存！")
                        st.rerun()

        st.divider()
        st.subheader("📝 配方库浏览")
        
        # 筛选与排序
        col_filter1, col_filter2, col_sort = st.columns([1, 2, 1])
        with col_filter1:
            filter_tier = st.multiselect("🔍 筛选等级", ["高级", "普通", "黑暗"])
        with col_filter2:
            filter_ing = st.multiselect("🔍 包含特定食材", ingredient_names)
        with col_sort:
            sort_mode = st.selectbox("🔃 排序方式", ["默认", "等级 (高->低)", "等级 (低->高)", "数量 (少->多)"])

        # 数据处理
        display_recipes = []
        for i, r in enumerate(current_recipes):
            temp_r = r.copy()
            temp_r['original_index'] = i 
            display_recipes.append(temp_r)

        if filter_tier:
            display_recipes = [r for r in display_recipes if r['tier'] in filter_tier]
        if filter_ing:
            target_set = set(filter_ing)
            display_recipes = [r for r in display_recipes if not target_set.isdisjoint(set(r['ingredients']))]

        if sort_mode == "等级 (高->低)":
            display_recipes.sort(key=lambda x: {"高级":3,"普通":2,"黑暗":1}.get(x['tier'],0), reverse=True)
        elif sort_mode == "等级 (低->高)":
            display_recipes.sort(key=lambda x: {"高级":3,"普通":2,"黑暗":1}.get(x['tier'],0))
        elif sort_mode == "数量 (少->多)":
            display_recipes.sort(key=lambda x: len(x['ingredients']))

        st.caption(f"展示 {len(display_recipes)} / {len(current_recipes)} 条")
        
        for recipe in display_recipes:
            idx = recipe['original_index']
            with st.container(border=True):
                col_info, col_imgs, col_del = st.columns([1, 4, 1])
                with col_info:
                    color = {"高级": "green", "普通": "orange", "黑暗": "grey"}.get(recipe['tier'], "black")
                    st.markdown(f"**:{color}[{recipe['tier']}]**")
                with col_imgs:
                    img_cols = st.columns(len(recipe['ingredients']) + 1)
                    for i, ing_name in enumerate(recipe['ingredients']):
                        path = all_ingredients.get(ing_name)
                        if path:
                            with img_cols[i]:
                                st.image(path, width=40)
                                st.caption(ing_name)
                with col_del:
                    if st.button("删除", key=f"del_rec_{idx}"):
                        current_recipes.pop(idx)
                        save_recipes(current_recipes)
                        st.rerun()

        # 清理工具
        st.divider()
        st.markdown("### 🛠️ 数据维护工具")
        if st.button("🧹 一键清理重复配方", type="secondary"):
            if not current_recipes:
                st.warning("无数据。")
            else:
                unique_map = {}
                orig_cnt = len(current_recipes)
                for recipe in current_recipes:
                    key = frozenset(recipe['ingredients'])
                    unique_map[key] = recipe
                deduped = list(unique_map.values())
                rm_cnt = orig_cnt - len(deduped)
                if rm_cnt > 0:
                    save_recipes(deduped)
                    st.success(f"✨ 已清理 {rm_cnt} 条重复数据")
                    st.rerun()
                else:
                    st.info("数据很干净。")

# ==========================================
# Tab 3: 拍照识别
# ==========================================
with tab3:
    st.subheader("3. 截图分析与计算")
    uploaded_shot = st.file_uploader("上传游戏画面截图", type=['jpg', 'png'])
    
    # 这里的验证逻辑改了，直接用后端加载的变量
    if uploaded_shot and API_KEY:
        st.image(uploaded_shot, caption="分析目标", width=300)
        
        if st.button("🚀 开始识别与计算", type="primary"):
            if not all_ingredients:
                st.error("图鉴是空的！")
            else:
                with st.spinner('AI 正在分析...'):
                    b64_img = encode_image(uploaded_shot)
                    # 使用全局配置的 KEY 和 URL
                    detected_names = identify_ingredients(
                        API_KEY, BASE_URL, MODEL_NAME, b64_img, list(all_ingredients.keys())
                    )
                    
                    if not detected_names:
                        st.warning("未识别到已知食材。")
                    else:
                        st.write("👁️ **识别结果：**")
                        d_cols = st.columns(8)
                        for i, d_name in enumerate(detected_names):
                            path = all_ingredients.get(d_name)
                            if path:
                                with d_cols[i % 8]:
                                    st.image(path, width=50)
                                    st.caption(d_name)
                        
                        st.divider()
                        
                        match_results = []
                        detected_set = set(detected_names)
                        for recipe in current_recipes:
                            if set(recipe['ingredients']).issubset(detected_set):
                                match_results.append(recipe)
                        
                        if match_results:
                            match_results.sort(key=lambda x: {"高级":3,"普通":2,"黑暗":1}.get(x['tier'],0), reverse=True)
                            best = match_results[0]
                            
                            if best['tier'] == "高级":
                                st.balloons()
                                st.success("🎉 恭喜！可制作【高级料理】！")
                            else:
                                st.info(f"💡 发现 {len(match_results)} 种组合")

                            for res in match_results:
                                with st.container():
                                    st.markdown(f"### {res['tier']} 配方")
                                    r_cols = st.columns(len(res['ingredients']) + 1)
                                    for k, r_name in enumerate(res['ingredients']):
                                        path = all_ingredients.get(r_name)
                                        with r_cols[k]:
                                            st.image(path, width=60)
                                            st.caption(r_name)
                                    st.write("---")
                        else:
                            st.warning("⚠️ 食材不足以合成已知配方。")