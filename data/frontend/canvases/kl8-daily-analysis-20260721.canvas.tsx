import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  LineChart,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

const HIT_TREND = [
  { period: "182", HE5: 1, Tr5: 1, AI5: 2 },
  { period: "183", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "184", HE5: 1, Tr5: 0, AI5: 1 },
  { period: "185", HE5: 0, Tr5: 1, AI5: 1 },
  { period: "186", HE5: 1, Tr5: 3, AI5: 2 },
  { period: "187", HE5: 3, Tr5: 2, AI5: 1 },
  { period: "188", HE5: 2, Tr5: 1, AI5: 1 },
  { period: "189", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "190", HE5: 0, Tr5: 0, AI5: 0 },
  { period: "191", HE5: 1, Tr5: 0, AI5: 2 },
];

const MODULE_LIFT = [
  { label: "HE5", lift: 1.04 },
  { label: "Tr5", lift: 0.96 },
  { label: "Tr12", lift: 0.93 },
  { label: "AI5", lift: 0.96 },
  { label: "AI12", lift: 0.93 },
];

const RECS = [
  { channel: "HE5", picks: "02 23 32 46 70", note: "首席战略官主通道" },
  { channel: "Trinity5", picks: "23 40 42 43 44", note: "EF0.50 RW0.20 FO0.30" },
  { channel: "Trinity12", picks: "02 23 27 30 33 36 40 42 43 44 74 75", note: "三维融合" },
  { channel: "AI5", picks: "02 05 32 46 53", note: "置信度精选" },
  { channel: "AI12", picks: "02 05 32 46 53 71 01 06 18 23 27 29", note: "综合拦截" },
  { channel: "Golden", picks: "02 23 42", note: "多维共振" },
  { channel: "mRMR", picks: "12 33 39 69 77 30 75 27 10 42 11 06", note: "熵控筛选" },
  { channel: "纯净池高置信", picks: "38 33 02", note: "LR软回退主输出" },
  { channel: "纯净池旧规则", picks: "38 33 02 55", note: "评分>=3" },
  { channel: "纯净池LR", picks: "38 33 02", note: "影子候选" },
  { channel: "纯净池全量", picks: "38 33 02 12 53 55 10 69 80 77 01 45", note: "12码" },
  { channel: "爆发Top5", picks: "70 80 35 39 07", note: "方案2精选" },
  { channel: "防守Top3", picks: "71 37 55", note: "建议回避" },
  { channel: "跨规则共识", picks: "35 40", note: "多规则同时推荐" },
];

const REVIEW_ROWS = [
  { module: "HE5", hit: "1/5", lift: "0.80x", detail: "命中 42" },
  { module: "Trinity5", hit: "0/5", lift: "0.00x", detail: "全空" },
  { module: "Trinity12", hit: "3/12", lift: "1.00x", detail: "1 42 55" },
  { module: "AI5", hit: "2/5", lift: "1.60x", detail: "23 32" },
  { module: "AI12", hit: "3/12", lift: "1.00x", detail: "23 32 42" },
  { module: "纯净池旧规则", hit: "2/4", lift: "2.00x", detail: "6 55" },
  { module: "纯净池全量", hit: "4/8", lift: "2.00x", detail: "2 6 53 55" },
  { module: "爆发Top5", hit: "1/5", lift: "0.80x", detail: "55" },
  { module: "防守Top3", hit: "3/3", lift: "—", detail: "回避 51 61 65" },
  { module: "Golden", hit: "3/6", lift: "2.00x", detail: "1 42 55" },
];

export default function Kl8DailyAnalysis20260721() {
  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 1120 }}>
      <Stack gap={6}>
        <H1>快乐8 每日分析控制面板</H1>
        <Text tone="secondary">
          2026-07-21 · 目标期 2026192 · 开奖复盘 2026191 · Source:
          reports/daily_analysis_report_20260721.md
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
          <Pill tone="info" size="sm">
            KL Z=1.22σ
          </Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="1.04x" label="近10期 HE5 Lift" tone="warning" />
        <Stat value="0.96x" label="近10期 AI5 Lift" />
        <Stat value="REFERENCE" label="内部提纯状态" tone="warning" />
        <Stat value="无需调整" label="深度优化决策" tone="success" />
      </Grid>

      <Callout tone="warning" title="命中率与优化结论">
        近10期主通道 Lift 贴近随机基线（HE5 1.04x / Tr5 0.96x / AI5
        0.96x），统计上无显著优势。自学习已冻结；极高阶三元模块已在 v4.2
        因历史 Lift≈0.80x 移除。本期不做新优化，持续监控即可。
      </Callout>

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>近10期命中数趋势 (Top5通道)</CardHeader>
          <CardBody>
            <LineChart
              categories={HIT_TREND.map((d) => d.period)}
              series={[
                { name: "HE5", data: HIT_TREND.map((d) => d.HE5) },
                { name: "Tr5", data: HIT_TREND.map((d) => d.Tr5) },
                { name: "AI5", data: HIT_TREND.map((d) => d.AI5) },
              ]}
              height={220}
            />
            <Spacer height={8} />
            <Text tone="secondary" size="sm">
              Source: 日报复盘表 2026182–2026191 · Y轴=命中码数/5
            </Text>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>近10期平均 Lift 对比</CardHeader>
          <CardBody>
            <BarChart
              categories={MODULE_LIFT.map((d) => d.label)}
              series={[{ name: "Lift", data: MODULE_LIFT.map((d) => d.lift) }]}
              height={220}
            />
            <Spacer height={8} />
            <Text tone="secondary" size="sm">
              随机基线 = 1.00x · Source: 近10期均值
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Stack gap={8}>
        <H2>上期 2026191 复盘</H2>
        <Text tone="secondary">
          开奖: 01 02 05 06 13 15 23 28 32 34 37 42 45 46 53 55 71 73 75 77
        </Text>
        <Table
          columns={[
            { key: "module", header: "模块", width: 140 },
            { key: "hit", header: "命中", width: 80 },
            { key: "lift", header: "Lift", width: 80 },
            { key: "detail", header: "明细" },
          ]}
          rows={REVIEW_ROWS}
        />
      </Stack>

      <Divider />

      <Stack gap={8}>
        <H2>今日 2026192 各通道推荐</H2>
        <Table
          columns={[
            { key: "channel", header: "通道", width: 130 },
            { key: "picks", header: "号码" },
            { key: "note", header: "说明", width: 160 },
          ]}
          rows={RECS}
        />
      </Stack>

      <Grid columns={3} gap={12}>
        <Card>
          <CardHeader>钻石级共振 (≥4模块)</CardHeader>
          <CardBody>
            <Text weight="semibold">02 · 23</Text>
            <Text tone="secondary" size="sm">
              HE5 ∩ Trinity ∩ AI ∩ Golden
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>金级共振 (3模块)</CardHeader>
          <CardBody>
            <Text weight="semibold">27 · 33 · 42</Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>风险提示</CardHeader>
          <CardBody>
            <Text size="sm">Level 1 弱信号防御 · 输出系数 0.5x</Text>
            <Text size="sm" tone="secondary">
              KL Z-Score 1.22σ · 未触发熔断
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Callout tone="info" title="修复与落地摘要">
        已修复 data_validator 自动修复后仍报失败的假阴性；补抓
        2026191；同步 Excel/热码/格式化；跑通今日日报并物理校验存在。
      </Callout>
    </Stack>
  );
}
