# Bili_v2_MIMO - B站弹幕与评论统计工具 v2.0

## ✨ 功能特性

- ✅ **弹幕收集** - 使用protobuf解析，支持并发获取
- ✅ **评论收集** - 使用Wbi签名，支持主评论和子评论
- ✅ **断点续传** - 中断后可继续，不丢失进度
- ✅ **自适应限流** - 遇到412自动降速，成功后恢复
- ✅ **多种输入** - 支持BV号、ep/ss号、视频URL、合集URL
- ✅ **完整导出** - 生成多种Excel报表

---

## 📁 目录结构

```
Bili_v2_MIMO/
├── main.py                          # 主入口
├── bili_stats/
│   ├── __init__.py
│   ├── models.py                    # 数据模型
│   ├── client.py                    # HTTP客户端（Wbi签名、限流）
│   ├── resolver.py                  # 视频信息解析
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── danmaku.py               # 弹幕收集器
│   │   └── comments.py              # 评论收集器
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── repository.py            # 数据库仓库
│   │   └── exporter.py              # Excel导出
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── input.py                 # 输入解析
│   │   └── progress.py              # 进度条
│   └── proto/                       # Protobuf定义
│       ├── dm.proto
│       └── dm_pb2.py
├── tests/                           # 测试文件
├── requirements.txt
└── README.md
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests pandas openpyxl protobuf
```

### 2. 编译Protobuf（如果需要）

```bash
cd bili_stats/proto
protoc --python_out=. dm.proto
```

### 3. 准备Cookie

将B站Cookie保存到 `cookie.txt` 文件：

```
SESSDATA=xxx; bili_jct=xxx
```

### 4. 运行

```bash
# 基本使用
python main.py BV1nAJK6PEwh --cookie-file cookie.txt

# 使用URL
python main.py https://www.bilibili.com/video/BV1nAJK6PEwh/

# 导出已有数据
python main.py BV1nAJK6PEwh --export-only

# 重新开始
python main.py BV1nAJK6PEwh --cookie-file cookie.txt --restart
```

---

## 📊 输出文件

运行完成后，会在输出目录生成以下文件：

```
Results/
└── 《视频标题》/
    ├── 001-分P标题/
    │   ├── 弹幕明细.xlsx          # 所有弹幕详情
    │   ├── 弹幕统计.xlsx          # 弹幕内容统计
    │   ├── 弹幕用户排行.xlsx      # 弹幕发送者排行
    │   ├── 完整评论.xlsx          # 所有评论
    │   └── 评论用户统计.xlsx      # 评论用户统计
    ├── 视频信息.xlsx              # 视频基本信息
    ├── 全局弹幕统计.xlsx          # 所有分P弹幕统计
    ├── 全局弹幕用户排行.xlsx      # 所有分P弹幕用户排行
    ├── 全局评论统计.xlsx          # 评论统计
    ├── 评论用户排行.xlsx          # 评论用户排行
    ├── 分集概览.xlsx              # 分集信息汇总
    └── data.db                    # SQLite数据库（断点续传用）
```

---

## ⚙️ 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | B站视频URL、BV号等 | 必填 |
| `--cookie` | Cookie字符串 | - |
| `--cookie-file` | Cookie文件路径 | - |
| `--database` | 数据库路径 | 自动创建 |
| `--output-dir` | 输出目录 | Results |
| `--restart` | 重新开始 | - |
| `--export-only` | 仅导出 | - |
| `--max-attempts` | 最大重试次数 | 5 |
| `--request-delay` | 最小请求间隔(秒) | 0.05 |
| `--concurrency` | 最大并发数 | 6 |
| `--no-progress` | 关闭进度条 | - |

---

## 🔧 架构设计

### 模块职责

| 模块 | 职责 |
|------|------|
| `client.py` | HTTP请求、Wbi签名、自适应限流 |
| `models.py` | 数据模型定义 |
| `resolver.py` | 解析视频信息、获取剧集列表 |
| `collectors/danmaku.py` | 弹幕收集（protobuf解析） |
| `collectors/comments.py` | 评论收集（Wbi签名） |
| `storage/repository.py` | SQLite数据库操作 |
| `storage/exporter.py` | Excel报表导出 |
| `utils/input.py` | 输入格式解析 |
| `utils/progress.py` | 进度条显示 |

### 自适应限流

```python
# 遇到412/429时
limiter.record_throttle()  # 并发减半，延迟加倍

# 成功请求后
limiter.record_success()   # 逐步恢复并发和延迟
```

### 断点续传

- 弹幕：记录已获取的分段号
- 评论：记录cursor游标
- 子评论：记录页码

---

## 📝 注意事项

1. **Cookie有效期** - Cookie通常有效期约30天
2. **请求频率** - 脚本会自动控制请求频率，避免触发风控
3. **弹幕限制** - B站API限制，每个视频最多获取约6000条弹幕
4. **存储空间** - 大量弹幕和评论需要较多存储空间

---

## 🐛 常见问题

### Q: 如何获取Cookie？

A: 登录B站 → F12打开开发者工具 → Network标签 → 刷新页面 → 找到Cookie字段

### Q: 遇到412错误怎么办？

A: 脚本会自动处理，降低请求频率并重试。如果持续出现，可以：
- 增加 `--request-delay` 参数
- 减少 `--concurrency` 参数
- 等待一段时间后重试

### Q: 如何继续中断的任务？

A: 直接重新运行相同命令即可，脚本会自动从断点继续

---

## 📄 许可证

本工具仅供学习交流使用，请遵守B站相关服务条款。
