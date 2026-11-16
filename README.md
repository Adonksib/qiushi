# 求是·考点｜2026 全年《求是》要点提炼站

把《求是》杂志 2026 年每一期，自动变成一份可读、可背、可打印的备考材料。

- **自动收录**：抓取求是网《求是》各期目录与全文，新一期上线当天入库
- **逐期提炼**：核心主线、专题要点、大概率出题方向（申论 / 常识 / 面试）、可直接用的金句
- **每期 PDF**：A4 排版，含提炼与全文，适合打印批注
- **零后端**：纯静态站点，GitHub Pages 直接托管，无需服务器与数据库

> 文字版权归原作者与求是杂志社所有。本站仅作个人学习研究使用，不作商业用途，引用请以原刊为准。

---

## 一、快速开始（本地）

```bash
pip install -r requirements.txt

python scripts/scrape.py              # 抓取全部期次（增量，已有期次会跳过）
python scripts/build_site.py --out dist   # 生成静态站点
python scripts/build_pdf.py --dist dist   # 生成每期 PDF（需要本机 Chrome/Edge）

# 本地预览
python -m http.server 8080 --directory dist
# 打开 http://localhost:8080
```

Windows 下如果 `python` 命令不可用，用 `py` 代替。

### 只重建某一期

```bash
python scripts/scrape.py --issue 22 --force
python scripts/build_site.py --out dist
python scripts/build_pdf.py --dist dist --issue 22
```

---

## 二、部署到 GitHub Pages

### 1. 建仓库并推送

```bash
git init
git add .
git commit -m "feat: 求是考点站初版"
git branch -M main
git remote add origin https://github.com/<你的用户名>/qiushi-exam.git
git push -u origin main
```

### 2. 打开 Pages

仓库 → **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。

推送后 `.github/workflows/update.yml` 会自动跑一次，完成后站点地址是：

```
https://<你的用户名>.github.io/qiushi-exam/
```

### 3. （可选）开启自动提炼

抓取和排版不需要任何密钥。但**要点提炼**由大模型生成，需要配一个 API Key：

| 位置 | 名称 | 说明 |
| --- | --- | --- |
| Settings → Secrets and variables → **Secrets** | `LLM_API_KEY` | 必填，任意 OpenAI 兼容服务的 Key |
| Settings → Secrets and variables → **Variables** | `LLM_BASE_URL` | 可选，默认 `https://api.deepseek.com` |
| Settings → Secrets and variables → **Variables** | `LLM_MODEL` | 可选，默认 `deepseek-chat` |

没配 Key 也能正常部署，站点会展示「全文 + 目录」，提炼区留空并提示整理中；配了 Key 之后，工作流每次抓到新期会自动生成提炼。

> 用 DeepSeek、通义千问、Kimi、智谱等任何兼容 `/v1/chat/completions` 协议的服务都可以，改 `LLM_BASE_URL` 和 `LLM_MODEL` 即可。

### 4. 自动更新节奏

工作流每天北京时间 **09:30** 跑一次（`.github/workflows/update.yml` 里的 cron），做四件事：

1. `scrape.py` 增量抓取新期次
2. `make_digest.py --missing` 为没有提炼的期次生成提炼
3. `build_site.py` + `build_pdf.py` 重建站点与 PDF
4. 提交数据变动、部署到 Pages

《求是》是半月刊（每月 1 日、16 日前后出版），每天跑一次已经足够及时。想改时间就调整 cron（注意是 **UTC**，北京时间减 8 小时）。

---

## 三、目录结构

```
qiushi-2026/
├── scripts/
│   ├── scrape.py       # 求是网 → data/issues/*.json（目录 + 全文）
│   ├── make_digest.py  # data/issues/*.json → data/digests/*.json（大模型提炼）
│   ├── build_site.py   # 数据 → dist/ 静态站点
│   └── build_pdf.py    # dist/print/*.html → dist/pdf/*.pdf（headless Chrome）
├── data/
│   ├── index.json          # 期次索引（自动生成）
│   ├── issues/2026-22.json # 单期全文数据
│   └── digests/2026-22.json# 单期提炼数据（人工或模型生成）
├── site/assets/        # 样式与前端脚本（不参与构建，直接拷贝）
├── dist/               # 构建产物（已 gitignore，由 Actions 部署）
└── .github/workflows/update.yml
```

### 数据结构

`data/issues/2026-22.json`：

```jsonc
{
  "year": 2026, "issue": 22, "published": "2026-11-16",
  "toc_url": "…", "article_count": 22, "total_chars": 81887,
  "articles": [
    {
      "title": "携手共建亚太命运共同体",
      "url": "https://www.qstheory.cn/…",
      "author": "习近平",
      "category": "习近平重要文章",
      "paragraphs": ["一", "亚太各经济体利益交融…"],
      "chars": 2958
    }
  ]
}
```

`data/digests/2026-22.json` 的字段见 `scripts/make_digest.py` 中的 prompt，核心是
`theme / one_line / overview / keywords / topics / exam / quotes`。

**金句有硬校验**：`make_digest.py` 会把每条 `quotes[].text` 拿去和原文逐字比对，
对不上（模型改写或编造）的直接剔除。宁可少一条，也不让你背错。

---

## 四、想改点什么

| 需求 | 改哪里 |
| --- | --- |
| 换年份（抓 2027 年） | `scripts/scrape.py` 顶部 `YEAR = 2026` |
| 换配色 | `site/assets/style.css` 里 `:root` 的 `--red`、`--paper` 等变量 |
| 改提炼的写法/口径 | `scripts/make_digest.py` 里的 `SYSTEM` 与 `USER_TMPL` |
| 手动修正某期提炼 | 直接编辑 `data/digests/2026-22.json`，然后重新 `build_site.py` |
| 改 PDF 版式 | `site/assets/style.css` 末尾 `@media print` 段 |

手工写提炼也完全可以：复制 `data/digests/2026-22.json` 改内容，不用跑模型。

---

## 五、免责与边界

- 站点只抓取求是网**公开发布**的页面内容，不含付费电子刊
- 抓取有节奏控制（每篇间隔 0.45–0.8 秒），请勿去掉延时高频请求
- 提炼与考点判断属于**辅助整理**，不等于命题预测；政策表述请以官方原文为准
- 若原站改版导致抓取失效，调整 `scripts/scrape.py` 里的选择器即可
