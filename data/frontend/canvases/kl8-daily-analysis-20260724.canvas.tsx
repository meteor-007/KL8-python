import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
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
  { period: "185", HE5: 0, Tr5: 1, AI5: 1 },
  { period: "186", HE5: 1, Tr5: 3, AI5: 2 },
  { period: "187", HE5: 3, Tr5: 2, AI5: 1 },
  { period: "188", HE5: 2, Tr5: 1, AI5: 1 },
  { period: "189", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "190", HE5: 0, Tr5: 0, AI5: 0 },
  { period: "191", HE5: 1, Tr5: 0, AI5: 2 },
  { period: "192", HE5: 3, Tr5: 0, AI5: 2 },
  { period: "193", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "194", HE5: 2, Tr5: 1, AI5: 2 },
];

const MODULE_LIFT = [
  { label: "HE5", lift: 1.28 },
  { label: "Tr5", lift: 0.96 },
  { label: "Tr12", lift: 1.0 },
  { label: "AI5", lift: 1.04 },
  { label: "AI12", lift: 1.03 },
];

const RECS = [
  { channel: "HE5", picks: "46 74 51 48 37", note: "评分序 · 首席主通道" },
  { channel: "Trinity5", picks: "38 50 53 71 75", note: "EF0.50 RW0.20 FO0.30" },
  { channel: "Trinity12", picks: "15 30 38 46 50 52 53 62 71 73 74 75", note: "三维融合" },
  { channel: "AI5", picks: "19 28 36 37 46", note: "置信度精选" },
  { channel: "AI12", picks: "19 28 36 37 46 48 51 54 66 10 12 16", note: "综合拦截" },
  { channel: "Golden", picks: "15 30 46 62 75", note: "多维共振" },
  { channel: "mRMR", picks: "12 33 39 77 69 30 42 27 10 78 23 61", note: "熵控筛选" },
  { channel: "纯净池高置信", picks: "53 38 11", note: "LR软回退主输出" },
  { channel: "纯净池旧规则", picks: "53 38 11 55 02", note: "评分>=3" },
  { channel: "纯净池LR", picks: "53 38 11", note: "影子候选" },
  { channel: "纯净池全量", picks: "53 38 11 55 27 02 46", note: "7码" },
  { channel: "爆发Top5", picks: "15 55 56 75 46", note: "方案2精选" },
  { channel: "防守Top3", picks: "32 35 77", note: "建议回避" },
  { channel: "跨规则共识", picks: "15", note: "多规则同时推荐" },
  { channel: "钻石共振", picks: "46", note: "≥4模块 · 仅参考" },
  { channel: "金级共振", picks: "15 30 75", note: "3模块 · 仅参考" },
];

const REVIEW_ROWS = [
  { module: "HE5", hit: "2/5", lift: "1.60x", detail: "47 51" },
  { module: "Trinity5", hit: "1/5", lift: "0.80x", detail: "74" },
  { module: "Trinity12", hit: "4/12", lift: "1.33x", detail: "29 47 51 74" },
  { module: "AI5", hit: "2/5", lift: "1.60x", detail: "37 51" },
  { module: "AI12", hit: "4/12", lift: "1.33x", detail: "02 05 37 51" },
  { module: "mRMR12", hit: "1/12", lift: "0.33x", detail: "12" },
  { module: "纯净池高置信", hit: "0/3", lift: "0.00x", detail: "全空" },
  { module: "纯净池全量", hit: "1/5", lift: "0.80x", detail: "02" },
  { module: "爆发Top5", hit: "2/5", lift: "1.60x", detail: "02 51" },
  { module: "防守Top3", hit: "3/3", lift: "—", detail: "回避52 55 61 / 误杀无" },
];

export default function Kl8DailyAnalysis20260724() {
  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 1120 }}>
      <Stack gap={6}>
        <H1>快乐8 每日分析控制面板</H1>
        <Text tone="secondary">
          2026-07-24 · 目标期 2026195 · 开奖复盘 2026194 · Source:
          reports/daily_analysis_report_20260724.md
        </Text>
        <Row gap={8}>
          <Pill tone="success" active>
            数据校验 PASS
          </Pill>
          <Pill tone="neutral" active>
            环境 平衡震荡期
          </Pill>
          <Pill tone="warning" active>
            信标 Level 1 · 0.5x
          </Pill>
          <Pill tone="neutral" active>
            自学习 FROZEN
          </Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="2026195" label="目标期号" />
        <Stat value="2/5" label="HE5上期命中" tone="success" />
        <Stat value="1.28x" label="HE5近10期Lift" tone="success" />
        <Stat value="无需调整" label="优化决策" />
      </Grid>

      <Callout tone="info" title="优化结论">
        近10期 HE5 Lift=1.28x 略优于随机；Trinity/AI 贴近基线。提纯区分力
        1.90x（VALID，仅参考不写参）。门控 FROZEN，维持三维精简架构 v4.2。
      </Callout>

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>近10期 Top5 命中走势</CardHeader>
          <CardBody>
            <LineChart
              data={HIT_TREND}
              xKey="period"
              series={[
                { key: "HE5", label: "HE5", tone: "accent" },
                { key: "Tr5", label: "Trinity5", tone: "neutral" },
                { key: "AI5", label: "AI5", tone: "warning" },
              ]}
              height={220}
            />
            <Text tone="secondary" size="small">
              Source: 日报复盘 · 期号后缀 185–194 · Y轴=命中码数/5
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>近10期模块 Lift</CardHeader>
          <CardBody>
            <BarChart
              data={MODULE_LIFT}
              xKey="label"
              series={[{ key: "lift", label: "Lift (vs 25%基线)", tone: "accent" }]}
              height={220}
            />
            <Text tone="secondary" size="small">
              Source: 近10期真实对账 · 基线=1.0x
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <Stack gap={8}>
        <Text weight="semibold">2026194 复盘对账</Text>
        <Table
          headers={["模块", "命中", "Lift", "命中号/说明"]}
          rows={REVIEW_ROWS.map((r) => [r.module, r.hit, r.lift, r.detail])}
        />
      </Stack>

      <Divider />

      <Stack gap={8}>
        <Text weight="semibold">2026195 各通道推荐（可复制）</Text>
        <Table
          headers={["通道", "号码", "说明"]}
          rows={RECS.map((r) => [r.channel, r.picks, r.note])}
        />
      </Stack>

      <Spacer />
      <Text tone="secondary" size="small">
        KL=0.0796 (Z=0.19) · B3质量=0.74 · 纯净池WF Lift=1.21x · 提纯状态
        VALID · 版本 v4.2
      </Text>
    </Stack>
  );
}
