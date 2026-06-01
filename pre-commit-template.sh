#!/bin/bash
# Git预提交钩子模板
# 确保代码提交前通过工作空间规范检查

echo "🔍 Git预提交规范检查"
echo "======================"

# 获取项目根目录
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
PROJECT_NAME="$(basename "$PROJECT_ROOT")"

echo "项目: $PROJECT_NAME"
echo "路径: $PROJECT_ROOT"

# 检查是否在3d项目中（已有检查脚本）
if [ -f "$PROJECT_ROOT/src/scripts/check_compliance.py" ]; then
    echo "📋 运行项目合规性检查..."
    
    cd "$PROJECT_ROOT"
    python src/scripts/check_compliance.py
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ 提交被拒绝：项目不符合工作空间规范"
        echo ""
        echo "💡 建议:"
        echo "  1. 运行 'python src/scripts/check_compliance.py --fix' 自动修复问题"
        echo "  2. 查看检查输出，手动修复问题"
        echo "  3. 重新提交"
        echo ""
        exit 1
    fi
else
    echo "⚠️  项目缺少合规性检查脚本"
    echo ""
    echo "💡 建议:"
    echo "  1. 从工作空间根目录运行: python check_all_projects.py --create-templates"
    echo "  2. 或手动创建 src/scripts/check_compliance.py"
    echo "  3. 本次提交将继续，但建议尽快添加检查脚本"
    echo ""
    
    # 询问是否继续提交
    read -p "是否继续提交? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "提交已取消"
        exit 1
    fi
fi

# 检查根目录是否有禁止的文件类型
echo "📄 检查根目录禁止文件..."
PROHIBITED_FILES=0

# 检查图片文件
if ls "$PROJECT_ROOT"/*.png 2>/dev/null || \
   ls "$PROJECT_ROOT"/*.jpg 2>/dev/null || \
   ls "$PROJECT_ROOT"/*.gif 2>/dev/null; then
    echo "❌ 根目录发现图片文件，请移动到 outputs/visualizations/"
    PROHIBITED_FILES=1
fi

# 检查JSON文件
if ls "$PROJECT_ROOT"/*.json 2>/dev/null; then
    echo "❌ 根目录发现JSON文件，请移动到 configs/"
    PROHIBITED_FILES=1
fi

# 检查BAT文件（除configs目录外）
if find "$PROJECT_ROOT" -maxdepth 1 -name "*.bat" | grep -v "^$PROJECT_ROOT/configs/" | grep -q "."; then
    echo "❌ 根目录发现BAT文件，请移动到 configs/"
    PROHIBITED_FILES=1
fi

# 检查日志文件
if ls "$PROJECT_ROOT"/*.log 2>/dev/null; then
    echo "❌ 根目录发现日志文件，请移动到 outputs/logs/"
    PROHIBITED_FILES=1
fi

# 检查脚本文件是否在正确位置
if find "$PROJECT_ROOT" -maxdepth 1 -name "*.py" | grep -v "$PROJECT_ROOT/main.py" | grep -v "$PROJECT_ROOT/setup.py" | grep -q "."; then
    echo "❌ 根目录发现Python脚本文件，请移动到 src/scripts/"
    PROHIBITED_FILES=1
fi

if [ $PROHIBITED_FILES -eq 1 ]; then
    echo ""
    echo "❌ 提交被拒绝：根目录存在禁止的文件类型"
    echo ""
    echo "📋 工作空间规范要求:"
    echo "  • 图片文件 → outputs/visualizations/"
    echo "  • JSON文件 → configs/"
    echo "  • BAT文件 → configs/"
    echo "  • 日志文件 → outputs/logs/"
    echo "  • Python脚本 → src/scripts/ (除main.py)"
    echo ""
    exit 1
fi

# 检查目录结构
echo "📁 检查目录结构..."
MISSING_DIRS=0

if [ ! -d "$PROJECT_ROOT/src" ]; then
    echo "❌ 缺失 src/ 目录"
    MISSING_DIRS=1
fi

if [ ! -d "$PROJECT_ROOT/docs" ]; then
    echo "⚠️  缺失 docs/ 目录（建议创建）"
fi

if [ ! -d "$PROJECT_ROOT/outputs" ]; then
    echo "⚠️  缺失 outputs/ 目录（建议创建）"
fi

if [ $MISSING_DIRS -eq 1 ]; then
    echo ""
    echo "❌ 提交被拒绝：缺失必要目录"
    echo ""
    exit 1
fi

echo ""
echo "✅ 所有检查通过，允许提交"
echo "======================"
exit 0