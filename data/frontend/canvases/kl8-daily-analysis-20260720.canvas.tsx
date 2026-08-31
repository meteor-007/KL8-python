import {
  Card,
  CardBody,
  CardHeader,
  Callout,
  Divider,
  Grid,
  H1,
  H2,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
  BarChart,
  LineChart,
} from "cursor/canvas";

const HIT_TREND = [
  { period: "181", HE5: 1, Tr5: 0, AI5: 2 },
  { period: "182", HE5: 1, Tr5: 1, AI5: 2 },
  { period: "183", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "184", HE5: 1, Tr5: 0, AI5: 1 },
  { period: "185", HE5: 0, Tr5: 1, AI5: 1 },
  { period: "186", HE5: 1, Tr5: 3, AI5: 2 },
  { period: "187", HE5: 3, Tr5: 2, AI5: 1 },
  { period: "188", HE5: 2, Tr5: 1, AI5: 1 },
  { period: "189", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "190", HE5: 0, Tr5: 0, AI5: 0 },
];

const MODULE_LIFT = [
  { label: "Burst", lift: 1.26 },
  { label: "PP", lift: 1.08 },
  { label: "HE5", lift: 1.04 },
  { label: "AI5", lift: 0.96 },
  { label: "Tr5", lift: 0.96 },
  { label: "GC", lift: 0.95 },
  { label: "AI12", lift: 0.93 },
  { label: "Tr12", lift: 0.9 },
];

export default function DailyAnalysisDashboard() {
  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 1100 }}>
      <Stack gap={6}>
        <H1>快乐8 每日分析控制面板</H1>
        <Text tone="secondary">
          2026-07-20 · 目标期 2026191 · 开奖复盘 2026190 · Source:
          reports/daily_analysis_report_20260720.md
        </Text>
        <Row gap={8} style={{ flexWrap: "wrap" }}>
          <Pill tone="success" size="sm">
            数据校验全通过
          </Pill>
          <Pill tone="warning" size="sm">
            自学习冻结 WF=1.00
          </Pill>
          <Pill tone="warning" size="sm">
            信标 Level1 ×0.5
          </Pill>
          <Pill tone="neutral" size="sm">
            环境 平衡震荡期
          </Pill>
          <Pill tone="neutral" size="sm">
            EF0.50 RW0.20 FO0.30
          </Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="1.04x" label="近10期 HE5 Lift" tone="warning" />
        <Stat value="1.26x" label="近7期 爆发Top5 Lift" tone="success" />
        <Stat value="0.60x" label="提纯区分力(近5)" tone="danger" />
        <Stat value="无需调整" label="深度优化决策" />
      </Grid>

      <Callout tone="warning" title="命中率结论">
        近10期主通道整体贴近随机基线（HE5 平均命中 1.30/5，Lift=1.04x）。上期
        2026190 主通道全线失利，但方案2爆发Top5 命中 3/5（Lift=2.40x）。统计上未显著优于基线，不建议叠加新复杂优化；极速爆破/高阶三元/深度攻坚引擎已归档移除。
      </Callout>

      <H2>上期复盘 2026190</H2>
      <Text tone="secondary" size="small">
        开奖：02-03-07-10-23-30-32-39-40-41-42-44-45-46-51-53-59-61-67-80 · KL
        Z=0.09σ（未熔断）
      </Text>
      <Table
        headers={["模块", "命中", "Lift", "命中号码"]}
        columnAlign={["left", "right", "right", "left"]}
        rows={[
          ["HE5", "0/5", "0.00x", "—"],
          ["Trinity5", "0/5", "0.00x", "—"],
          ["Trinity12", "1/12", "0.33x", "30"],
          ["AI5", "0/5", "0.00x", "—"],
          ["AI12", "2/12", "0.67x", "3, 10"],
          ["mRMR12", "3/12", "1.00x", "30, 39, 42"],
          ["纯净池高置信", "1/3", "1.33x", "2"],
          ["爆发Top5", "3/5", "2.40x", "2, 30, 80"],
          ["跨规则共识", "2/5", "1.60x", "30, 80"],
          ["防守Top3", "2/3成功", "—", "误杀32"],
        ]}
        rowTone={[
          "danger",
          "danger",
          undefined,
          "danger",
          undefined,
          undefined,
          "success",
          "success",
          "success",
          undefined,
        ]}
      />

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>近10期 Top5 命中走势</CardHeader>
          <CardBody>
            <LineChart
              categories={HIT_TREND.map((d) => d.period)}
              series={[
                { name: "HE5", data: HIT_TREND.map((d) => d.HE5) },
                { name: "Trinity5", data: HIT_TREND.map((d) => d.Tr5) },
                { name: "AI5", data: HIT_TREND.map((d) => d.AI5) },
              ]}
              height={220}
            />
            <Text tone="secondary" size="small">
              X: 期号后缀(20261xx) · Y: 命中码数/5 · 随机基线≈1.25 · Source: 近10期日报
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>近10期模块平均 Lift</CardHeader>
          <CardBody>
            <BarChart
              categories={MODULE_LIFT.map((d) => d.label)}
              series={[{ name: "Lift", data: MODULE_LIFT.map((d) => d.lift) }]}
              height={220}
            />
            <Text tone="secondary" size="small">
              Lift=命中率/25% · 1.0x=随机 · Burst N=7 其余 N=10
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <H2>今日推荐 2026191</H2>
      <Table
        headers={["通道", "号码", "说明"]}
        rows={[
          ["Hidden Energy 5", "41 42 44 54 70", "主推荐"],
          ["Trinity Top5", "11 29 33 43 44", "三维融合"],
          ["Trinity Top12", "01 11 12 27 29 33 40 42 43 44 55 79", "EF/RW/FO"],
          ["AI Top5", "11 23 32 44 56", "对照组"],
          ["AI Top12", "11 23 32 44 56 61 67 26 20 21 38 42", "对照组"],
          ["Golden Core", "01 11 12 33 42 55", "多维共振"],
          ["mRMR Top12", "77 69 33 38 12 39 30 07 27 42 11 67", "熵控"],
          ["纯净池高置信", "38 33 20", "LR软回退"],
          ["旧规则>=3", "38 33 06 55", "阶跃规则"],
          ["爆发Top5", "55 33 78 70 38", "近10期Lift最高通道"],
          ["防守Top3", "65 61 51", "回避"],
          ["跨规则共识", "11 25 33 55", "方案2"],
        ]}
      />

      <Card>
        <CardHeader>Hidden Energy 5 评分明细</CardHeader>
        <CardBody>
          <Text size="small" tone="secondary">
            公式：候选集 Min-Max 归一化后 EF_n×1.0 + RW_n×0.8 + FO_n×0.5 · B3质量分
            0.86
          </Text>
          <Spacer />
          <Table
            headers={["#", "号", "EF_n", "RW_n", "FO_n", "Score"]}
            columnAlign={["right", "right", "right", "right", "right", "right"]}
            rows={[
              ["1", "42", "1.000", "0.000", "0.454", "1.227"],
              ["2", "44", "0.870", "0.000", "0.611", "1.175"],
              ["3", "54", "0.113", "0.884", "0.488", "1.065"],
              ["4", "70", "0.059", "1.000", "0.397", "1.058"],
              ["5", "41", "0.838", "0.000", "0.369", "1.022"],
            ]}
          />
        </CardBody>
      </Card>

      <H2>内部提纯（任务4.5）</H2>
      <Callout tone="danger" title="区分力无效 — 仅作参考">
        近5期钻石级/铜级命中率比值≈0.595x（小于1.0）。内部提纯降级为纯参考，不驱动选号权重；钻石阈值维持≥4模块。
      </Callout>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>钻石级号码（≥4模块）</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Row gap={10}>
                <Text weight="semibold">33</Text>
                <Text size="small" tone="secondary">
                  Trinity · mRMR · 纯净池 · Golden · Burst
                </Text>
              </Row>
              <Row gap={10}>
                <Text weight="semibold">42</Text>
                <Text size="small" tone="secondary">
                  HE5 · Trinity · AI · mRMR · Golden
                </Text>
              </Row>
              <Row gap={10}>
                <Text weight="semibold">11</Text>
                <Text size="small" tone="secondary">
                  Trinity · AI · mRMR · Golden (FDR)
                </Text>
              </Row>
              <Row gap={10}>
                <Text weight="semibold">38</Text>
                <Text size="small" tone="secondary">
                  AI · mRMR · 纯净池 · Burst
                </Text>
              </Row>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>金级号码（3模块）</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Row gap={10}>
                <Text weight="semibold">12</Text>
                <Text size="small" tone="secondary">
                  Trinity · mRMR · Golden
                </Text>
              </Row>
              <Row gap={10}>
                <Text weight="semibold">44</Text>
                <Text size="small" tone="secondary">
                  HE5 · Trinity · AI
                </Text>
              </Row>
              <Row gap={10}>
                <Text weight="semibold">55</Text>
                <Text size="small" tone="secondary">
                  Trinity · Golden · Burst
                </Text>
              </Row>
            </Stack>
          </CardBody>
        </Card>
      </Grid>
      <Text size="small" tone="secondary">
        三维自洽：动态权重 EF 贴边 0.50；HE5 中 EF 主导的 42/44 在 Trinity Top12
        内，41 为 HE5 独有。极高阶三元/极速爆破已移除。
      </Text>

      <Divider />
      <H2>问题修复与闭环</H2>
      <Table
        headers={["问题", "纠正", "验证"]}
        rows={[
          ["kl8_history 滞后2天(至189)", "fetch_kl8_history → 新增2026190", "校验A新鲜度通过"],
          ["热码缺期 191/183/175/167", "generate_hot --fill-missing + process", "校验F对齐通过"],
          ["Excel开奖Sheet未同步190", "sync_history_to_excel 双Sheet", "校验C/D通过"],
          ["二次复盘误报未找到预测", "autonomous_learner.review 幂等复用", "复用2026190成功"],
          ["提纯区分力0.60x无效", "降级REFERENCE_ONLY，不改选号权重", "learner_state.purify_meta"],
        ]}
      />

      <Callout tone="neutral" title="任务3 优化决策">
        经统计检验，当前命中率未显著优于随机基线，不建议增加新优化方案。当前三维
        EF/RW/FO + HE5 + 自学习门控(Lift大于1.1解锁)架构维持现状，持续监控。
      </Callout>

      <Text tone="secondary" size="small">
        报告：reports/daily_analysis_report_20260720.md · 门控 WF Lift=1.0043 · 权重
        EF0.40/RW0.30/FO0.30 · 策略 balanced
      </Text>
    </Stack>
  );
}
