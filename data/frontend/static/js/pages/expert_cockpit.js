/**
 * K8 page module: expert_cockpit (专家作战室)
 * 手机快捷录入、绝杀对冲雷达与逐期自动开奖复盘
 */
(function () {
  if (!window.K8Pages || typeof window.K8Pages.register !== 'function') {
    console.error('[K8Pages] registry missing — load k8_pages.js first (expert_cockpit)');
    return;
  }

  window.K8Pages.register(function (vueApi, ctx) {
    const { ref, reactive, watch, nextTick } = vueApi;
    const { addLog, activeTab } = ctx;

    const expertSubTab = ref('radar'); // 'radar' | 'input' | 'review'
    const expertData = ref({
      period: '2026304',
      expert_count: 9,
      kill_numbers: [1, 6, 16, 17, 24, 25, 31, 34, 47, 48, 58, 59, 62, 69, 72],
      resonance_radar: [],
      expert_cards: [],
      safe_gold_pool: []
    });

    const expertPeriods = ref([]);
    const expertSelectedPeriod = ref('2026304');
    const expertReview = ref({
      period: '2026304',
      is_drawn: false,
      draw_numbers: [],
      kill_review: { accuracy: '0%', success_count: 0, hit_count: 0, killed_success_list: [], killed_failed_list: [] },
      mvp_expert: '',
      expert_reviews: []
    });

    const expertRawInputText = ref('');

    const expertInputForm = reactive({
      period: '2026304',
      kill_text: '01 06 16 17 24 25 31 34 47 48 58 59 62 69 72',
      faruxue_p3: '12 14 66',
      faruxue_p4: '12 47 66 74',
      xiaoxiang_p3: '09 20 32',
      meimei_point: '12',
      meimei_trio: '30 31 32',
      meimei_tail: '79 80',
      beige_dan: '52',
      beige_tuo: '07 10 17 30 64',
      yudi_dans: '52 05',
      yudi_duels: '11/25, 32/39, 51/78, 02/09, 12/38, 50/73',
      juanzi_dan: '39',
      juanzi_p4: '24 39 58 76',
      dage_p6: '24 27 33 37 25 68',
      laozhao_p3: '17 22 23',
      guanjia_p6: '28 38 48 68 77 20'
    });

    // ──────────────── 数据加载与交互 ────────────────
    const loadExpertPeriods = async () => {
      try {
        const res = await fetch('/api/expert/periods');
        if (res.ok) {
          const json = await res.json();
          if (json.status === 'success' && Array.isArray(json.periods)) {
            expertPeriods.value = json.periods;
            if (json.periods.length > 0 && !expertSelectedPeriod.value) {
              expertSelectedPeriod.value = json.periods[0].period;
            }
          }
        }
      } catch (err) {
        console.error('Failed to load expert periods:', err);
      }
    };

    const loadExpertData = async (period) => {
      try {
        const p = period || expertSelectedPeriod.value || '';
        const url = p ? `/api/expert/current?period=${encodeURIComponent(p)}` : '/api/expert/current';
        const res = await fetch(url);
        if (res.ok) {
          const json = await res.json();
          if (json.status === 'success') {
            expertData.value = json;
            expertSelectedPeriod.value = json.period;
            expertInputForm.period = json.period;
            if (json.kill_numbers && Array.isArray(json.kill_numbers)) {
              expertInputForm.kill_text = json.kill_numbers.map(n => (n < 10 ? '0' + n : n)).join(' ');
            }
          }
        }
      } catch (err) {
        console.error('Failed to load expert data:', err);
      }
    };

    const loadExpertReview = async (period) => {
      try {
        const p = period || expertSelectedPeriod.value || expertData.value.period || '2026304';
        const res = await fetch(`/api/expert/review/${encodeURIComponent(p)}`);
        if (res.ok) {
          const json = await res.json();
          expertReview.value = json;
        }
      } catch (err) {
        console.error('Failed to load expert review:', err);
      }
    };

    // ──────────────── 智能文本快速切分 ────────────────
    const parseRawText = async () => {
      if (!expertRawInputText.value || !expertRawInputText.value.trim()) {
        alert('请先在文本框中粘贴微信群或记事本内容！');
        return;
      }
      try {
        const res = await fetch('/api/expert/quick-parse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ raw_text: expertRawInputText.value })
        });
        if (res.ok) {
          const json = await res.json();
          if (json.status === 'success' && json.parsed) {
            const p = json.parsed;
            if (p.kill_numbers && p.kill_numbers.length > 0) {
              expertInputForm.kill_text = p.kill_numbers.map(n => (n < 10 ? '0' + n : n)).join(' ');
            }
            const exp = p.experts || {};
            if (exp['发如雪']) {
              if (exp['发如雪'].pick3) expertInputForm.faruxue_p3 = exp['发如雪'].pick3.join(' ');
              if (exp['发如雪'].pick4) expertInputForm.faruxue_p4 = exp['发如雪'].pick4.join(' ');
            }
            if (exp['小巷'] && exp['小巷'].pick3) expertInputForm.xiaoxiang_p3 = exp['小巷'].pick3.join(' ');
            if (exp['妹妹']) {
              if (exp['妹妹'].focus_point) expertInputForm.meimei_point = String(exp['妹妹'].focus_point);
              if (exp['妹妹'].trio) expertInputForm.meimei_trio = exp['妹妹'].trio.join(' ');
              if (exp['妹妹'].tail_pairs) expertInputForm.meimei_tail = exp['妹妹'].tail_pairs.join(' ');
            }
            if (exp['北哥']) {
              if (exp['北哥'].dan) expertInputForm.beige_dan = String(exp['北哥'].dan);
              if (exp['北哥'].combos) {
                const tuos = exp['北哥'].combos.map(c => c[1]);
                expertInputForm.beige_tuo = tuos.join(' ');
              }
            }
            if (exp['娟子']) {
              if (exp['娟子'].dan) expertInputForm.juanzi_dan = String(exp['娟子'].dan);
              if (exp['娟子'].pick4) expertInputForm.juanzi_p4 = exp['娟子'].pick4.join(' ');
            }
            if (exp['大哥'] && exp['大哥'].pick6) expertInputForm.dage_p6 = exp['大哥'].pick6.join(' ');
            if (exp['老赵'] && exp['老赵'].pick3) expertInputForm.laozhao_p3 = exp['老赵'].pick3.join(' ');
            if (exp['管家'] && exp['管家'].pick6) expertInputForm.guanjia_p6 = exp['管家'].pick6.join(' ');

            if (addLog) addLog('✅ 微信文本智能解析完成，已自动填入对应专家输入框！', 'success');
          }
        }
      } catch (err) {
        console.error('Failed to quick-parse text:', err);
      }
    };

    // ──────────────── 提交保存 ────────────────
    const parseNums = (str) => {
      if (!str) return [];
      const matches = String(str).match(/\d+/g) || [];
      return matches.map(Number).filter(n => n >= 1 && n <= 80);
    };

    const submitExpertForm = async () => {
      try {
        const period = (expertInputForm.period || '').trim();
        if (!period) {
          alert('请输入期号！');
          return;
        }

        const kill_numbers = parseNums(expertInputForm.kill_text);

        // 组装 9 位专家
        const experts = {};

        // 发如雪
        const faruxue_p3 = parseNums(expertInputForm.faruxue_p3);
        const faruxue_p4 = parseNums(expertInputForm.faruxue_p4);
        if (faruxue_p3.length > 0 || faruxue_p4.length > 0) {
          experts['发如雪'] = {
            type: '选三 / 选四',
            pick3: faruxue_p3,
            pick4: faruxue_p4,
            notes: '红底快手风，重合骨架码 12, 66'
          };
        }

        // 小巷
        const xiaoxiang_p3 = parseNums(expertInputForm.xiaoxiang_p3);
        if (xiaoxiang_p3.length > 0) {
          experts['小巷'] = { type: '选三单式', pick3: xiaoxiang_p3, notes: '绿底精选选三' };
        }

        // 妹妹
        const meimei_p = parseNums(expertInputForm.meimei_point);
        const meimei_trio = parseNums(expertInputForm.meimei_trio);
        const meimei_tail = parseNums(expertInputForm.meimei_tail);
        if (meimei_p.length > 0 || meimei_trio.length > 0 || meimei_tail.length > 0) {
          experts['妹妹'] = {
            type: '点位 / 连号 / 尾号',
            focus_point: meimei_p[0] || 12,
            trio: meimei_trio,
            tail_pairs: meimei_tail,
            notes: '微信 breeze 推荐，关注点位与连号'
          };
        }

        // 北哥
        const beige_dan = parseNums(expertInputForm.beige_dan)[0] || 52;
        const beige_tuo = parseNums(expertInputForm.beige_tuo);
        if (beige_tuo.length > 0) {
          experts['北哥'] = {
            type: '选二单式 (主胆拖5码)',
            dan: beige_dan,
            combos: beige_tuo.map(t => [beige_dan, t]),
            notes: '粉橙卡片，52主胆拖5码'
          };
        }

        // 雨滴
        const yudi_dans = parseNums(expertInputForm.yudi_dans);
        // 解析二选一，如 "11/25, 32/39"
        const duelPairs = [];
        const duelSegments = (expertInputForm.yudi_duels || '').split(/[,，;\n]/);
        let duelIdx = 1;
        for (const seg of duelSegments) {
          const pair = parseNums(seg);
          if (pair.length >= 2) {
            duelPairs.push({ pair: [pair[0], pair[1]], label: `第${duelIdx++}组` });
          }
        }
        if (yudi_dans.length > 0 || duelPairs.length > 0) {
          experts['雨滴'] = {
            type: '主胆 + 二选一对决',
            dans: yudi_dans,
            duels: duelPairs,
            notes: '黄底双表格对决推荐'
          };
        }

        // 娟子
        const juanzi_dan = parseNums(expertInputForm.juanzi_dan)[0] || 39;
        const juanzi_p4 = parseNums(expertInputForm.juanzi_p4);
        if (juanzi_p4.length > 0) {
          experts['娟子'] = {
            type: '银胆 + 独荐4码',
            dan: juanzi_dan,
            pick4: juanzi_p4,
            notes: '强推定海银胆 39'
          };
        }

        // 大哥
        const dage_p6 = parseNums(expertInputForm.dage_p6);
        if (dage_p6.length > 0) {
          experts['大哥'] = { type: '精选6码', pick6: dage_p6, notes: '中后区6码出击' };
        }

        // 老赵
        const laozhao_p3 = parseNums(expertInputForm.laozhao_p3);
        if (laozhao_p3.length > 0) {
          experts['老赵'] = { type: '选三实战', pick3: laozhao_p3, notes: '前区小跨度选三' };
        }

        // 管家
        const guanjia_p6 = parseNums(expertInputForm.guanjia_p6);
        if (guanjia_p6.length > 0) {
          experts['管家'] = { type: '同尾特色6码', pick6: guanjia_p6, notes: '8尾同尾群号共振' };
        }

        const payload = {
          period: period,
          kill_numbers: kill_numbers,
          experts: experts
        };

        const res = await fetch('/api/expert/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          const json = await res.json();
          if (json.status === 'success') {
            if (addLog) addLog(`🎉 第 ${period} 期专家作战室数据已保存！`, 'success');
            await loadExpertPeriods();
            await loadExpertData(period);
            expertSubTab.value = 'radar';
          } else {
            alert('保存失败: ' + (json.message || '未知错误'));
          }
        }
      } catch (err) {
        console.error('Failed to submit expert form:', err);
        alert('提交出错: ' + err.message);
      }
    };

    // 监听 activeTab 自动激活加载
    if (activeTab) {
      watch(activeTab, (newTab) => {
        if (newTab === 'expert_cockpit') {
          loadExpertPeriods();
          loadExpertData();
        }
      });
    }

    // 默认预载
    loadExpertPeriods();
    loadExpertData();

    return {
      expertSubTab,
      expertData,
      expertPeriods,
      expertSelectedPeriod,
      expertReview,
      expertRawInputText,
      expertInputForm,
      loadExpertPeriods,
      loadExpertData,
      loadExpertReview,
      parseRawText,
      submitExpertForm
    };
  });
})();
