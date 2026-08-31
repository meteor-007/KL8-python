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
  { period: "184", HE5: 1, Tr5: 0, AI5: 1 },
  { period: "185", HE5: 0, Tr5: 1, AI5: 1 },
  { period: "186", HE5: 1, Tr5: 3, AI5: 2 },
  { period: "187", HE5: 3, Tr5: 2, AI5: 1 },
  { period: "188", HE5: 2, Tr5: 1, AI5: 1 },
  { period: "189", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "190", HE5: 0, Tr5: 0, AI5: 0 },
  { period: "191", HE5: 1, Tr5: 0, AI5: 2 },
  { period: "192", HE5: 3, Tr5: 0, AI5: 2 },
  { period: "193", HE5: 2, Tr5: 2, AI5: 1 },
];

const MODULE_LIFT = [
  { label: "HE5", lift: 1.2 },
  { label: "Tr5", lift: 0.88 },
  { label: "Tr12", lift: 0.93 },
  { label: "AI5", lift: 0.96 },
  { label: "AI12", lift: 1.0 },
];

const RECS = [
  { channel: "HE5", picks: "51 62 47 42 63", note: "评分序 · 首席主通道" },
  { channel: "Trinity5", picks: "42 53 63 71 74", note: "EF0.50 RW0.20 FO0.30" },
  { channel: "Trinity12", picks: "27 29 38 42 47 50 51 53 62 63 71 74", note: "三维融合" },
  { channel: "AI5", picks: "08 15 37 42 51", note: "置信度精选" },
  { channel: "AI12", picks: "08 15 37 42 51 71 14 01 02 05 09 53", note: "综合拦截" },
  { channel: "Golden", picks: "27 42 62", note: "多维共振" },
  { channel: "mRMR", picks: "12 33 77 69 30 27 18 10 42 07 11 61", note: "熵控筛选" },
  { channel: "纯净池高置信", picks: "53 38 01", note: "LR软回退主输出" },
  { channel: "纯净池旧规则", picks: "53 38 23", note: "评分>=3" },
  { channel: "纯净池LR", picks: "53 38 01", note: "影子候选" },
  { channel: "纯净池全量", picks: "01 02 23 38 53", note: "5码" },
  { channel: "爆发Top5", picks: "02 38 62 51 27", note: "方案2精选" },
  { channel: "防守Top3", picks: "52 55 61", note: "建议回避" },
  { channel: "跨规则共识", picks: "12 27 32 38", note: "多规则同时推荐" },
  { channel: "钻石共振", picks: "27 42 51 62", note: "≥4模块 · 仅参考" },
  { channel: "金级共振", picks: "38 53", note: "3模块 · 仅参考" },
];

const REVIEW_ROWS = [
  { module: "HE5", hit: "2/5", lift: "1.60x", detail: "15 75" },
  { module: "Trinity5", hit: "2/5", lift: "1.60x", detail: "29 71" },
  { module: "Trinity12", hit: "3/12", lift: "1.00x", detail: "29 52 71" },
  { module: "AI5", hit: "1/5", lift: "0.80x", detail: "51" },
  { module: "AI12", hit: "3/12", lift: "1.00x", detail: "15 51 75" },
  { module: "mRMR12", hit: "3/12", lift: "1.00x", detail: "30 42 61" },
  { module: "纯净池高置信", hit: "0/3", lift: "0.00x", detail: "全空" },
  { module: "纯净池全量", hit: "1/8", lift: "0.50x", detail: "71" },
  { module: "爆发Top5", hit: "2/5", lift: "1.60x", detail: "61 71" },
  { module: "防守Top3", hit: "1/3", lift: "—", detail: "回避25 / 误杀3,15" },
];

export default function Kl8DailyAnalysis20260723() {
  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 1120 }}>
      <Stack gap={6}>
        <H1>快乐8 每日分析控制面板</H1>
        <Text tone="secondary">
          2026-07-23 · 目标期 2026194 · 开奖复盘 2026193 · Source:
          reports/daily_analysis_report_20260723.md
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
        <Stat value="2026194" label="目标期号" />
        <Stat value="2/5" label="HE5上期命中" tone="success" />
        <Stat value="1.20x" label="HE5近10期Lift" tone="success" />
        <Stat value="无需调整" label="优化决策" />
      </Grid>

      <Callout tone="info" title="优化结论">
        近10期仅 HE5 Lift=1.20x 略优于随机；Trinity/AI 贴近基线。提纯区分力
        0.00x（REFERENCE_ONLY）。不新增复杂度，维持三维精简架构。
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
              Source: 日报复盘 · 期号后缀 184–193 · Y轴=命中码数/5
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
        <Text weight="semibold">2026193 复盘对账</Text>
        <Table
          headers={["模块", "命中", "Lift", "命中号/说明"]}
          rows={REVIEW_ROWS.map((r) => [r.module, r.hit, r.lift, r.detail])}
        />
      </Stack>

      <Divider />

      <Stack gap={8}>
        <Text weight="semibold">2026194 各通道推荐（可复制）</Text>
        <Table
          headers={["通道", "号码", "说明"]}
          rows={RECS.map((r) => [r.channel, r.picks, r.note])}
        />
      </Stack>

      <Spacer />
      <Text tone="secondary" size="small">
        KL=0.0804 (Z=0.27) · B3质量=0.92 · 纯净池WF Lift=1.21x · 提纯状态
        REFERENCE_ONLY
      </Text>
    </Stack>
  );
}
