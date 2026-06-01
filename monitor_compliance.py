#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作空间规范执行监控系统
定期监控工作空间所有项目的规范符合性，生成报告和提醒

使用方法:
    python monitor_compliance.py [--daily] [--weekly] [--report] [--notify]

参数:
    --daily: 生成每日监控报告
    --weekly: 生成每周监控报告
    --report: 生成详细HTML报告
    --notify: 发送通知（如邮件或消息）
"""

import os
import sys
import argparse
import json
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import subprocess

class ComplianceMonitor:
    """规范执行监控器"""
    
    def __init__(self, workspace_path):
        self.workspace_path = Path(workspace_path).absolute()
        self.reports_dir = self.workspace_path / 'compliance_reports'
        self.reports_dir.mkdir(exist_ok=True)
        
        # 监控配置
        self.config = {
            'daily_report_retention': 7,  # 保留7天日报
            'weekly_report_retention': 4,  # 保留4周周报
            'notification_threshold': 3,   # 连续3次不合格发送通知
            'projects_to_monitor': self.find_all_projects()
        }
    
    def find_all_projects(self):
        """查找所有需要监控的项目"""
        projects = []
        exclude_patterns = ['.git', '__pycache__', 'venv', 'env', 'node_modules']
        
        for item in self.workspace_path.iterdir():
            if item.is_dir():
                # 检查是否在排除列表中
                should_exclude = False
                for pattern in exclude_patterns:
                    if pattern in item.name:
                        should_exclude = True
                        break
                
                if should_exclude:
                    continue
                
                # 检查是否是项目
                has_src = (item / 'src').exists()
                has_readme = (item / 'README.md').exists()
                has_main = (item / 'main.py').exists()
                
                if has_src or has_readme or has_main:
                    projects.append({
                        'name': item.name,
                        'path': str(item),
                        'last_check': None,
                        'compliance_status': 'unknown',
                        'violations': [],
                        'check_count': 0,
                        'fail_count': 0,
                        'streak_failures': 0
                    })
        
        return projects
    
    def run_daily_check(self):
        """运行每日检查"""
        print("📅 运行每日规范检查...")
        timestamp = datetime.now().strftime("%Y%m%d")
        
        report_data = {
            'date': datetime.now().isoformat(),
            'type': 'daily',
            'projects': [],
            'summary': {
                'total': 0,
                'compliant': 0,
                'non_compliant': 0,
                'warnings': 0
            }
        }
        
        for project in self.config['projects_to_monitor']:
            print(f"  🔍 检查项目: {project['name']}")
            
            # 运行检查
            result = self.check_project(project['path'])
            
            # 更新项目状态
            project['last_check'] = datetime.now().isoformat()
            project['check_count'] += 1
            
            if result['compliant']:
                project['compliance_status'] = 'compliant'
                project['streak_failures'] = 0
                report_data['summary']['compliant'] += 1
            else:
                project['compliance_status'] = 'non_compliant'
                project['fail_count'] += 1
                project['streak_failures'] += 1
                project['violations'] = result['violations']
                report_data['summary']['non_compliant'] += 1
            
            report_data['projects'].append({
                'name': project['name'],
                'compliant': result['compliant'],
                'violations': result['violations'],
                'has_check_script': result['has_check_script']
            })
            
            report_data['summary']['total'] += 1
        
        # 保存报告
        report_file = self.reports_dir / f'daily_report_{timestamp}.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 每日报告已保存: {report_file}")
        
        # 清理旧报告
        self.cleanup_old_reports('daily')
        
        return report_data
    
    def run_weekly_summary(self):
        """运行每周总结"""
        print("📊 生成每周规范总结...")
        
        # 获取最近7天的日报
        daily_reports = []
        for report_file in self.reports_dir.glob('daily_report_*.json'):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                    daily_reports.append(report)
            except:
                continue
        
        if not daily_reports:
            print("⚠️  没有找到日报数据")
            return None
        
        # 按日期排序
        daily_reports.sort(key=lambda x: x['date'])
        
        # 生成周报
        week_start = datetime.now() - timedelta(days=7)
        weekly_data = {
            'period': {
                'start': week_start.isoformat(),
                'end': datetime.now().isoformat()
            },
            'type': 'weekly',
            'daily_reports_count': len(daily_reports),
            'project_stats': {},
            'trends': {},
            'recommendations': []
        }
        
        # 分析项目趋势
        project_stats = {}
        for project in self.config['projects_to_monitor']:
            project_name = project['name']
            project_stats[project_name] = {
                'total_checks': project['check_count'],
                'failures': project['fail_count'],
                'compliance_rate': 0,
                'current_status': project['compliance_status'],
                'streak_failures': project['streak_failures']
            }
            
            if project['check_count'] > 0:
                compliance_rate = (project['check_count'] - project['fail_count']) / project['check_count'] * 100
                project_stats[project_name]['compliance_rate'] = round(compliance_rate, 1)
        
        weekly_data['project_stats'] = project_stats
        
        # 生成建议
        recommendations = []
        for project_name, stats in project_stats.items():
            if stats['compliance_rate'] < 80:
                recommendations.append(f"项目 {project_name} 合规率较低 ({stats['compliance_rate']}%)，需要关注")
            
            if stats['streak_failures'] >= 3:
                recommendations.append(f"项目 {project_name} 连续{stats['streak_failures']}次检查不合格，需要立即整改")
        
        weekly_data['recommendations'] = recommendations
        
        # 保存周报
        timestamp = datetime.now().strftime("%Y%m%d")
        weekly_file = self.reports_dir / f'weekly_summary_{timestamp}.json'
        with open(weekly_file, 'w', encoding='utf-8') as f:
            json.dump(weekly_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 周报已保存: {weekly_file}")
        
        # 清理旧周报
        self.cleanup_old_reports('weekly')
        
        return weekly_data
    
    def check_project(self, project_path):
        """检查单个项目"""
        project_path = Path(project_path)
        
        # 检查是否有检查脚本
        check_script = project_path / 'src' / 'scripts' / 'check_compliance.py'
        has_check_script = check_script.exists()
        
        if has_check_script:
            # 使用项目检查脚本
            try:
                result = subprocess.run(
                    [sys.executable, str(check_script)],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
                
                compliant = result.returncode == 0
                violations = []
                
                if not compliant:
                    # 从输出中提取违规信息
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if '•' in line or '-' in line:
                            violation = line.strip(' •-')
                            if violation:
                                violations.append(violation)
                
                return {
                    'compliant': compliant,
                    'violations': violations,
                    'has_check_script': True,
                    'output': result.stdout
                }
                
            except Exception as e:
                return {
                    'compliant': False,
                    'violations': [f'检查脚本执行错误: {str(e)}'],
                    'has_check_script': True,
                    'output': str(e)
                }
        else:
            # 基本检查
            violations = []
            
            # 检查必要目录
            required_dirs = ['src', 'docs', 'outputs']
            for dir_name in required_dirs:
                if not (project_path / dir_name).exists():
                    violations.append(f'缺失目录: {dir_name}')
            
            # 检查根目录禁止文件
            prohibited_ext = ['.png', '.jpg', '.json', '.bat', '.log']
            for item in project_path.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext in prohibited_ext:
                        violations.append(f'根目录禁止文件: {item.name}')
            
            return {
                'compliant': len(violations) == 0,
                'violations': violations,
                'has_check_script': False,
                'output': '项目缺少检查脚本'
            }
    
    def cleanup_old_reports(self, report_type):
        """清理旧报告"""
        if report_type == 'daily':
            retention = self.config['daily_report_retention']
            pattern = 'daily_report_*.json'
        else:
            retention = self.config['weekly_report_retention']
            pattern = 'weekly_summary_*.json'
        
        report_files = list(self.reports_dir.glob(pattern))
        report_files.sort(reverse=True)  # 最新的在前面
        
        # 保留指定数量的报告
        if len(report_files) > retention:
            for old_file in report_files[retention:]:
                try:
                    old_file.unlink()
                    print(f"🗑️  清理旧报告: {old_file.name}")
                except:
                    pass
    
    def generate_html_report(self, report_data):
        """生成HTML报告"""
        print("🌐 生成HTML报告...")
        
        if report_data['type'] == 'daily':
            html = self.generate_daily_html(report_data)
            filename = f"daily_report_{datetime.now().strftime('%Y%m%d')}.html"
        else:
            html = self.generate_weekly_html(report_data)
            filename = f"weekly_summary_{datetime.now().strftime('%Y%m%d')}.html"
        
        html_file = self.reports_dir / filename
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"💾 HTML报告已保存: {html_file}")
        return html_file
    
    def generate_daily_html(self, report_data):
        """生成每日HTML报告"""
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>工作空间规范每日检查报告 - {datetime.now().strftime('%Y年%m月%d日')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .summary-item {{ display: inline-block; margin-right: 30px; }}
        .compliant {{ color: #4CAF50; font-weight: bold; }}
        .non-compliant {{ color: #f44336; font-weight: bold; }}
        .project-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .project-table th, .project-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        .project-table th {{ background-color: #4CAF50; color: white; }}
        .project-table tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .status-compliant {{ color: #4CAF50; }}
        .status-non-compliant {{ color: #f44336; }}
        .violations {{ color: #666; font-size: 0.9em; }}
        .timestamp {{ color: #888; font-size: 0.8em; text-align: right; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 工作空间规范每日检查报告</h1>
        <div class="timestamp">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        
        <div class="summary">
            <h2>📊 检查摘要</h2>
            <div class="summary-item">总项目数: <span class="compliant">{report_data['summary']['total']}</span></div>
            <div class="summary-item">符合规范: <span class="compliant">{report_data['summary']['compliant']}</span></div>
            <div class="summary-item">不符合规范: <span class="non-compliant">{report_data['summary']['non_compliant']}</span></div>
        </div>
        
        <h2>📁 项目检查详情</h2>
        <table class="project-table">
            <thead>
                <tr>
                    <th>项目名称</th>
                    <th>检查状态</th>
                    <th>检查脚本</th>
                    <th>违规问题</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for project in report_data['projects']:
            status_class = 'status-compliant' if project['compliant'] else 'status-non-compliant'
            status_text = '✅ 符合' if project['compliant'] else '❌ 不符合'
            script_text = '✅ 有' if project['has_check_script'] else '⚠️ 无'
            
            violations_html = '<br>'.join([f'• {v}' for v in project['violations']]) if project['violations'] else '无'
            
            html += f"""                <tr>
                    <td><strong>{project['name']}</strong></td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{script_text}</td>
                    <td class="violations">{violations_html}</td>
                </tr>
"""
        
        html += """            </tbody>
        </table>
        
        <div style="margin-top: 30px; padding: 15px; background: #e8f5e8; border-radius: 5px;">
            <h3>💡 建议与提醒</h3>
            <ul>
                <li>对于不符合规范的项目，请运行项目内的检查脚本查看具体问题</li>
                <li>缺少检查脚本的项目，请从工作空间根目录运行: <code>python check_all_projects.py --create-templates</code></li>
                <li>连续多次检查不合格的项目需要重点关注和整改</li>
            </ul>
        </div>
    </div>
</body>
</html>"""
        
        return html
    
    def generate_weekly_html(self, report_data):
        """生成每周HTML报告"""
        # 简化的周报HTML，实际实现会更复杂
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>工作空间规范每周总结 - {datetime.now().strftime('%Y年%m月%d日')}</title>
</head>
<body>
    <h1>📊 工作空间规范每周总结</h1>
    <p>周期: {report_data['period']['start']} 至 {report_data['period']['end']}</p>
    <p>共分析 {report_data['daily_reports_count']} 份日报</p>
    
    <h2>项目合规率统计</h2>
    <ul>
"""
        
        for project_name, stats in report_data['project_stats'].items():
            status_emoji = '✅' if stats['current_status'] == 'compliant' else '❌'
            html += f"""        <li>{status_emoji} {project_name}: 
            合规率 {stats['compliance_rate']}%, 
            检查{stats['total_checks']}次, 
            失败{stats['failures']}次
            {f'(连续{stats["streak_failures"]}次不合格)' if stats['streak_failures'] > 0 else ''}
        </li>
"""
        
        html += """    </ul>
    
    <h2>建议</h2>
    <ul>
"""
        
        for recommendation in report_data['recommendations']:
            html += f"        <li>{recommendation}</li>\n"
        
        html += """    </ul>
</body>
</html>"""
        
        return html
    
    def send_notification(self, report_data, recipients):
        """发送通知（示例实现）"""
        print("📧 发送通知...")
        
        # 这里只是示例，实际需要配置邮件服务器
        # 在实际使用中，可以集成邮件、Slack、企业微信等通知方式
        
        subject = f"工作空间规范检查报告 - {datetime.now().strftime('%Y-%m-%d')}"
        
        # 构建邮件内容
        message = MIMEMultipart()
        message['Subject'] = subject
        message['From'] = 'compliance@workspace.local'
        message['To'] = ', '.join(recipients)
        
        # 文本内容
        text_content = f"""
工作空间规范检查报告
====================

检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
检查类型: {report_data['type']}

📊 检查摘要:
  总项目数: {report_data['summary']['total']}
  符合规范: {report_data['summary']['compliant']}
  不符合规范: {report_data['summary']['non_compliant']}

📋 不符合规范的项目:
"""
        
        for project in report_data['projects']:
            if not project['compliant']:
                text_content += f"  • {project['name']}\n"
                for violation in project['violations']:
                    text_content += f"    - {violation}\n"
        
        text_content += """
💡 建议:
  1. 运行项目检查脚本查看具体问题
  2. 对于连续不合格的项目需要重点关注
  3. 缺少检查脚本的项目请创建模板

查看详细报告请访问工作空间 compliance_reports/ 目录
"""
        
        message.attach(MIMEText(text_content, 'plain'))
        
        # 在实际使用中，这里会发送邮件
        # try:
        #     with smtplib.SMTP('smtp.server.com', 587) as server:
        #         server.starttls()
        #         server.login('username', 'password')
        #         server.send_message(message)
        #     print("✅ 通知发送成功")
        # except Exception as e:
        #     print(f"❌ 通知发送失败: {e}")
        
        print("⚠️  通知功能需要配置邮件服务器，当前为演示模式")
        print("邮件内容预览:")
        print(text_content)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='工作空间规范执行监控系统')
    parser.add_argument('--daily', action='store_true', help='运行每日检查')
    parser.add_argument('--weekly', action='store_true', help='生成每周总结')
    parser.add_argument('--report', action='store_true', help='生成HTML报告')
    parser.add_argument('--notify', nargs='+', help='发送通知到指定邮箱')
    parser.add_argument('--workspace', type=str, default='.', help='工作空间路径')
    
    args = parser.parse_args()
    
    monitor = ComplianceMonitor(args.workspace)
    
    if args.daily:
        report_data = monitor.run_daily_check()
        
        if args.report:
            monitor.generate_html_report(report_data)
        
        if args.notify:
            monitor.send_notification(report_data, args.notify)
    
    elif args.weekly:
        report_data = monitor.run_weekly_summary()
        
        if report_data and args.report:
            monitor.generate_html_report(report_data)
        
        if report_data and args.notify:
            monitor.send_notification(report_data, args.notify)
    
    else:
        # 默认运行每日检查
        report_data = monitor.run_daily_check()
        
        if args.report:
            monitor.generate_html_report(report_data)
        
        if args.notify:
            monitor.send_notification(report_data, args.notify)
    
    print("\n🎯 监控任务完成")
    print("📁 报告保存在: compliance_reports/ 目录")

if __name__ == "__main__":
    main()