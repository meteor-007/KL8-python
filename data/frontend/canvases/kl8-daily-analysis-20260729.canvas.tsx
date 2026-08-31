import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Grid,
  H1,
  LineChart,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

const HIT_TREND = [
  { period: "190", HE5: 0, Tr5: 0, AI5: 0 },
  { period: "191", HE5: 1, Tr5: 0, AI5: 2 },
  { period: "192", HE5: 3, Tr5: 0, AI5: 2 },
  { period: "193", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "194", HE5: 2, Tr5: 1, AI5: 2 },
  { period: "195", HE5: 2, Tr5: 1, AI5: 3 },
  { period: "196", HE5: 1, Tr5: 1, AI5: 1 },
  { period: "197", HE5: 3, Tr5: 3, AI5: 2 },
  { period: "198", HE5: 2, Tr5: 2, AI5: 3 },
  { period: "199", HE5: 1, Tr5: 2, AI5: 0 },
];

const MODULE_LIFT = [
  { label: "HE5", lift: 1.36 },
  { label: "Tr5", lift: 0.96 },
  { label: "Tr12", lift: 1.07 },
  { label: "AI5", lift: 1.28 },
  { label: "AI12", lift: 1.0 },
];

const RECS = [
  { channel: "HE5", picks: "17 18 26 27 60", note: "评分序 · 首席主通道" },
  { channel: "Trinity5", picks: "15 16 19 27 75", note: "EF0.50 RW0.20 FO0.30" },
  { channel: "Trinity12", picks: "15 16 17 19 26 27 29 42 43 53 73 75", note: "三维融合" },
  { channel: "AI5", picks: "17 18 26 27 34", note: "置信度精选" },
  { channel: "AI12", picks: "17 18 26 27 34 44 55 58 31 68 11 53", note: "综合拦截" },
  { channel: "Golden", picks: "19 27 29 42 53 73 75", note: "多维共振" },
  { channel: "mRMR", picks: "12 39 75 42 30 18 69 10 27 19 06 53", note: "熵控筛选" },
  { channel: "纯净池高置信", picks: "02 10 42", note: "LR软回退主输出" },
  { channel: "纯净池旧规则", picks: "02 10 42 53", note: "评分>=3" },
  { channel: "纯净池LR", picks: "02 10 42", note: "影子候选" },
  { channel: "爆发Top5", picks: "75 76 12 49 42", note: "方案2精选" },
  { channel: "防守Top3", picks: "44 79 55", note: "建议回避" },
  { channel: "跨规则共识", picks: "12 75", note: "多规则同时推荐" },
  { channel: "钻石共振", picks: "27 42 53 75", note: "≥4模块 · 仅参考" },
  { channel: "金级共振", picks: "17 18 19 26", note: "3模块 · 仅参考" },
];

const REVIEW_ROWS = [
  { module: "HE5", hit: "1/5", lift: "0.80x", detail: "50" },
  { module: "Trinity5", hit: "2/5", lift: "1.60x", detail: "50 53" },
  { module: "Trinity12", hit: "3/12", lift: "1.00x", detail: "27 50 53" },
  { module: "AI5", hit: "0/5", lift: "0.00x", detail: "全空" },
  { module: "AI12", hit: "2/12", lift: "0.67x", detail: "14 79" },
  { module: "mRMR12", hit: "2/12", lift: "0.67x", detail: "18 27" },
  { module: "纯净池高置信", hit: "0/3", lift: "0.00x", detail: "全空" },
  { module: "纯净池全量", hit: "2/12", lift: "0.67x", detail: "27 53" },
  { module: "爆发Top5", hit: "2/5", lift: "1.60x", detail: "27 53" },
  { module: "防守Top3", hit: "2/3", lift: "—", detail: "回避24 46 / 误杀55" },
];

export default function Kl8DailyAnalysis20260729() {
  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 1120 }}>
      <Stack gap={6}>
        <H1>快乐8 每日分析控制面板</H1>
        <Text tone="secondary">
          2026-07-29 · 目标期 2026200 · 开奖复盘 2026199 · Source:
          reports/daily_analysis_report_20260729.md
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
        <Stat value="2026200" label="目标期号" />
        <Stat value="1/5" label="HE5上期命中" tone="warning" />
        <Stat value="1.36x" label="HE5近10期Lift" tone="success" />
        <Stat value="无需调整" label="优化决策" />
      </Grid>

      <Callout tone="info" title="优化结论">
        近10期 HE5 Lift=1.36x、Tr12=1.07x、AI12=1.00x，主通道略优但无明确深度优化方案。
        提纯区分力 0.00x（REFERENCE_ONLY）。门控 FROZEN（WF=1.0043），维持三维精简架构 v4.2。
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
              Source: daily reports · periods 2026190–2026199 · hits per Top5
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>近10期通道平均 Lift</CardHeader>
          <CardBody>
            <BarChart
              data={MODULE_LIFT}
              xKey="label"
              series={[{ key: "lift", label: "Lift (x)", tone: "accent" }]}
              height={220}
            />
            <Text tone="secondary" size="small">
              Baseline random = 1.0x · HE5 remains primary channel
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Card>
        <CardHeader trailing={<Pill tone="warning" active>2026199</Pill>}>
          上期复盘对账
        </CardHeader>
        <CardBody>
          <Text tone="secondary">
            开奖: 04 14 17 18 20 21 26 27 29 34 44 48 50 53 55 59 62 67 76 79
          </Text>
          <Table
            columns={[
              { key: "module", header: "通道", width: 140 },
              { key: "hit", header: "命中", width: 80 },
              { key: "lift", header: "Lift", width: 80 },
              { key: "detail", header: "明细" },
            ]}
            rows={REVIEW_ROWS}
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader trailing={<Pill tone="success" active>目标 2026200</Pill>}>
          今日各通道推荐
        </CardHeader>
        <CardBody>
          <Table
            columns={[
              { key: "channel", header: "通道", width: 140 },
              { key: "picks", header: "号码" },
              { key: "note", header: "说明", width: 180 },
            ]}
            rows={RECS}
          />
        </CardBody>
      </Card>

      <Callout tone="neutral" title="可复制主推 HE5">
        17 18 26 27 60
      </Callout>
    </Stack>
  );
}
