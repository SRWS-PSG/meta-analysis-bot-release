#!/usr/bin/env python3
"""
サブグループforest plotのslabエラー修正案

問題: "length of the slab argument does not correspond to the size of the original dataset"
原因: escalc/rma.mhでNA行やゼロセル行が削除された後、slabベクトル長さが不一致

修正アプローチ:
1. 有効行の事前フィルタリング
2. slab参照方式の統一
3. データ整合性の確保
"""

# 修正されたRテンプレート部分のPythonコード生成
def generate_fixed_binary_subgroup_template():
    """
    修正されたサブグループ解析テンプレート
    
    主な修正点:
    1. 有効データ行の事前確定
    2. slabを列名参照に統一
    3. drop00=TRUEによる行削除への対応
    """
    
    return """
# ==== 修正版: サブグループ解析テンプレート ====

# 1. データ読み込み後、有効行を事前確定
print("ステップ1: 有効データ行の確定")
valid_rows <- with(dat, 
    !is.na({ai}) & !is.na({bi}) & !is.na({ci}) & !is.na({di}) &
    {ai} >= 0 & {bi} >= 0 & {ci} >= 0 & {di} >= 0 &
    ({ai} + {bi}) > 0 & ({ci} + {di}) > 0
)

print(paste("元データ行数:", nrow(dat)))
print(paste("有効データ行数:", sum(valid_rows)))

# 有効データのみでフィルタ
dat_valid <- dat[valid_rows, ]

# 2. escalc()で効果量計算（slabは列名参照）
print("ステップ2: 効果量計算")
dat_valid <- escalc(
    measure = "{measure}",
    ai = {ai}, bi = {bi}, ci = {ci}, di = {di},
    data = dat_valid,
    slab = {study_id_column},  # 列名で参照
    add = 0, to = "none"
)

print(paste("escalc後の行数:", nrow(dat_valid)))

# 3. サブグループ別解析（rma.mhも列名参照）
print("ステップ3: サブグループ別解析")
subgroup_col <- "{subgroup_column}"
subgroup_levels <- unique(dat_valid[[subgroup_col]])
subgroup_levels <- subgroup_levels[!is.na(subgroup_levels)]

print(paste("サブグループ数:", length(subgroup_levels)))

# 各サブグループの解析
subgroup_results <- list()
for (sg_level in subgroup_levels) {{
    sg_data <- dat_valid[dat_valid[[subgroup_col]] == sg_level & !is.na(dat_valid[[subgroup_col]]), ]
    
    if (nrow(sg_data) > 1) {{
        print(paste("解析中:", sg_level, "- 研究数:", nrow(sg_data)))
        
        # rma.mh()でサブグループ解析
        sg_res <- rma.mh(
            ai = {ai}, bi = {bi}, ci = {ci}, di = {di},
            data = sg_data,
            measure = "{measure}",
            slab = {study_id_column},  # 列名で参照
            add = 0, to = "none",
            drop00 = TRUE, correct = TRUE
        )
        
        subgroup_results[[sg_level]] <- sg_res
        print(paste("完了:", sg_level, "- 実際の研究数:", sg_res$k))
    }} else {{
        print(paste("スキップ:", sg_level, "- 研究数不足 (n=", nrow(sg_data), ")"))
    }}
}}

# 4. フォレストプロット用データ準備
print("ステップ4: フォレストプロット準備")

# 全体解析（プロット用）
res_for_plot <- rma.mh(
    ai = {ai}, bi = {bi}, ci = {ci}, di = {di},
    data = dat_valid,
    measure = "{measure}",
    slab = {study_id_column},  # 列名参照
    add = 0, to = "none",
    drop00 = TRUE, correct = TRUE
)

print(paste("プロット用解析完了 - 研究数:", res_for_plot$k))

# 5. サブグループ別フォレストプロット
print("ステップ5: サブグループフォレストプロット生成")

# 各サブグループのプロット
for (sg_level in names(subgroup_results)) {{
    sg_res <- subgroup_results[[sg_level]]
    
    # サブグループデータのフィルタリング
    sg_data <- dat_valid[dat_valid[[subgroup_col]] == sg_level & !is.na(dat_valid[[subgroup_col]]), ]
    
    # forest()呼び出し時はslabを明示的に指定
    forest(
        sg_res,
        slab = sg_data[[{study_id_column}]],  # データから直接取得
        main = paste("Subgroup:", sg_level),
        atransf = if("{measure}" %in% c("OR", "RR")) exp else I,
        refline = if("{measure}" %in% c("OR", "RR")) 0 else 0
    )
}}

print("サブグループフォレストプロット生成完了")
"""

def generate_key_fixes():
    """
    主要な修正ポイント
    """
    return {{
        "fix_1_valid_rows": {{
            "description": "有効行の事前確定",
            "code": """
# 有効行を事前に確定（NA、負値、ゼロ分母を除外）
valid_rows <- with(dat, 
    !is.na({ai}) & !is.na({bi}) & !is.na({ci}) & !is.na({di}) &
    {ai} >= 0 & {bi} >= 0 & {ci} >= 0 & {di} >= 0 &
    ({ai} + {bi}) > 0 & ({ci} + {di}) > 0
)
dat_valid <- dat[valid_rows, ]
""",
            "benefit": "metaforの内部行削除を回避"
        }},
        
        "fix_2_column_reference": {{
            "description": "slab参照方式の統一",
            "code": """
# escalc()とrma.mh()でslabを列名参照に統一
escalc(..., data = dat_valid, slab = {study_id_column})
rma.mh(..., data = dat_valid, slab = {study_id_column})
""",
            "benefit": "データフレーム内の列を自動参照、長さ不整合を回避"
        }},
        
        "fix_3_explicit_slab": {{
            "description": "forest()でのslab明示",
            "code": """
# forest()では実際のデータから直接slabを取得
forest(sg_res, slab = sg_data[[{study_id_column}]], ...)
""",
            "benefit": "フィルタ済みデータに対応する正確なslabを使用"
        }},
        
        "fix_4_size_validation": {{
            "description": "データサイズ検証",
            "code": """
# 各ステップでデータサイズを検証
print(paste("escalc後の行数:", nrow(dat_valid)))
print(paste("rma.mh後の研究数:", res$k))
print(paste("slab長さ:", length(slab_vector)))
""",
            "benefit": "問題の早期発見とデバッグ情報提供"
        }}
    }}

if __name__ == "__main__":
    print("=== サブグループforest plotのslabエラー修正案 ===")
    print()
    print("問題: length of the slab argument does not correspond to the size of the original dataset")
    print()
    print("修正アプローチ:")
    
    fixes = generate_key_fixes()
    for fix_id, fix_info in fixes.items():
        print(f"\\n{fix_id}: {fix_info['description']}")
        print(f"効果: {fix_info['benefit']}")
    
    print()
    print("修正されたテンプレート例:")
    print(generate_fixed_binary_subgroup_template())