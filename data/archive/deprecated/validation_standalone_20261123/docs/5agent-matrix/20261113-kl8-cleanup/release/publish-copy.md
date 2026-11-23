【KL8 三项目收尾完成 · 2026-11-13】

✅ C 项目
· 5 个文档路径回退到实际目录「微积分分区」
· 补 requirements.txt（numpy/openpyxl/torch/pytest 按本机版本锁定）
· 补 pytest.ini，根目录 pytest 40 passed（不再误收 legacy）
· 清理回灌 .bak，.gitignore 增加 *.bak
· 提交 407ba73 已推送

✅ A 项目
· 任务板 T6 收尾，G1 新增测试数更正为 18
· file/ 输入目录 796.8 MiB → 513.6 MiB
· 旧期 18 个图表归档到 backup/kl8_inputs/（zip 校验通过）
· 保留最近三期、3 个母版、294/295/298 测试 fixture
· A 全量 359 passed；data_sync exit 0

✅ B 项目
· 本地目录已删除
· 两个闲置会话已归档
· 代码/历史保留在 GitHub

✅ 质量
· 独立审查 PASS：0 High / 0 Medium
· 预注册 KL8-2026-11-11-001 仍 active，冻结校验通过
· 未改模型、权重、生产 Top5

后续：按每日指令继续 300 期预注册，剩余 298 期。不构成投注建议。