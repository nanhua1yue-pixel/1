/**
 * 采购补货决策系统 - 前端应用
 */
const { createApp, ref, reactive, computed, onMounted, watch, nextTick } = Vue;

const app = createApp({
    setup() {
        // ==================== 状态 ====================
        const activeMenu = ref('dashboard');
        const loading = ref(false);
        const submitting = ref(false);
        const currentPeriod = ref(new Date().toISOString().slice(0, 7));
        const zhCn = ElementPlusLocaleZhCn;

        // 仪表盘数据
        const dashboardData = reactive({
            total: 0, pending: 0, processing: 0, completed: 0,
            completion_rate: 0, kpi_score: 0, commission_amount: 0,
            total_stock_amount: 0, total_return_amount: 0,
            score_detail: {}, action_stats: {}, can_return_stats: {},
        });

        // 滞销品列表
        const slowList = ref([]);
        const slowTotal = ref(0);
        const selectedRows = ref([]);
        const filterForm = reactive({
            status: '', can_return: '', action_type: '',
            keyword: '', sort_by: 'stock_amount', sort_order: 'desc',
            page: 1, page_size: 20,
        });

        // 处理弹窗
        const processDialogVisible = ref(false);
        const processForm = reactive({
            sku_id: null, sku_code: '', goods_name: '',
            current_stock: 0, stock_amount: 0, monthly_sales_30d: 0,
            can_return: '', return_reason: '',
            action_type: '', action_detail: '', action_deadline: '',
        });

        // 完成弹窗
        const completeDialogVisible = ref(false);
        const completeForm = reactive({
            sku_id: null, sku_code: '',
            actual_return_amount: 0, actual_clear_amount: 0, result_note: '',
        });

        // 日志弹窗
        const logDialogVisible = ref(false);
        const logList = ref([]);

        // KPI数据
        const kpiData = ref({});
        const commissionData = ref({});

        // ==================== 计算属性 ====================
        const pageTitle = computed(() => {
            const titles = {
                'dashboard': '工作台',
                'slow-list': '滞销品列表',
                'slow-dashboard': '滞销品处理进度',
                'kpi-score': '月度绩效评分',
                'kpi-commission': '提成计算',
                'kpi-history': '历史记录',
                'inv-overview': '库存总览',
                'inv-stockout': '缺货预警',
            };
            return titles[activeMenu.value] || '采购补货决策系统';
        });

        const systemHealthType = computed(() => {
            const rate = dashboardData.completion_rate;
            if (rate >= 95) return 'success';
            if (rate >= 80) return 'warning';
            return 'danger';
        });

        const completionCardClass = computed(() => {
            const rate = dashboardData.completion_rate;
            if (rate >= 95) return 'stat-card-ok';
            if (rate >= 60) return 'stat-card-warning';
            return 'stat-card-danger';
        });

        // 考核影响分析数据
        const impactData = computed(() => {
            const rate = dashboardData.completion_rate;
            const score = dashboardData.kpi_score;
            const commission = dashboardData.commission_amount;
            const coeff = rate >= 100 ? 1.1 : (rate < 80 ? 0.9 : 1.0);
            const penalty = rate < 60 ? -10 : 0;

            return [
                {
                    item: '考核得分 (满10分)',
                    standard: '≥95%=10分 | 90-95%=7分 | 80-90%=3分 | 60-80%=1分 | <60%=0分',
                    current: `${score}分`,
                    value: `${score}/10分`,
                    type: score >= 7 ? 'success' : (score >= 3 ? 'warning' : 'danger'),
                },
                {
                    item: '提成金额 (最高700元)',
                    standard: '≥95%=700元 | 90-95%=400元 | 80-90%=100元 | <80%=0元',
                    current: `${commission}元`,
                    value: `${commission}元`,
                    type: commission >= 400 ? 'success' : (commission > 0 ? 'warning' : 'danger'),
                },
                {
                    item: '行为系数 (C项)',
                    standard: '100%→×1.1 | 80-100%→×1.0 | <80%→×0.9',
                    current: `×${coeff}`,
                    value: coeff > 1 ? '提成+10%' : (coeff < 1 ? '提成-10%' : '无影响'),
                    type: coeff > 1 ? 'success' : (coeff < 1 ? 'danger' : 'info'),
                },
                {
                    item: '铁律扣分',
                    standard: '<60%触发: 考核额外-10分',
                    current: penalty === 0 ? '未触发' : `${penalty}分`,
                    value: penalty === 0 ? '安全' : '-10分!',
                    type: penalty === 0 ? 'success' : 'danger',
                },
                {
                    item: '一票否决 (D项)',
                    standard: '连续2月<60% → B部分提成全部取消',
                    current: rate >= 60 ? '安全' : '危险',
                    value: rate >= 60 ? '不触发' : '可能取消B部分!',
                    type: rate >= 60 ? 'success' : 'danger',
                },
            ];
        });

        // ==================== 方法 ====================

        // API请求
        async function api(url, method = 'GET', data = null) {
            try {
                const config = { method, url };
                if (method === 'GET' && data) {
                    config.params = data;
                } else if (data) {
                    config.data = data;
                }
                const res = await axios(config);
                return res.data;
            } catch (err) {
                console.error('API Error:', err);
                ElementPlus.ElMessage.error(err.response?.data?.message || '请求失败');
                throw err;
            }
        }

        // 加载仪表盘
        async function loadDashboard() {
            try {
                const res = await api('/api/slow-moving/dashboard', 'GET', {
                    period: currentPeriod.value
                });
                if (res.code === 0) {
                    Object.assign(dashboardData, res.data);
                }
            } catch (e) {
                // 系统刚部署时数据为空，显示默认值
                console.log('Dashboard data not available yet');
            }
        }

        // 加载滞销品列表
        async function loadSlowList() {
            loading.value = true;
            try {
                const params = { ...filterForm, period: currentPeriod.value };
                Object.keys(params).forEach(k => {
                    if (params[k] === '' || params[k] === null) delete params[k];
                });
                const res = await api('/api/slow-moving/list', 'GET', params);
                if (res.code === 0) {
                    slowList.value = res.data.items;
                    slowTotal.value = res.data.total;
                }
            } catch (e) {
                slowList.value = [];
                slowTotal.value = 0;
            }
            loading.value = false;
        }

        // 处理弹窗
        function openProcessDialog(row) {
            Object.assign(processForm, {
                sku_id: row.id, sku_code: row.sku_code, goods_name: row.goods_name,
                current_stock: row.current_stock, stock_amount: row.stock_amount,
                monthly_sales_30d: row.monthly_sales_30d,
                can_return: '', return_reason: '',
                action_type: '', action_detail: '', action_deadline: '',
            });
            processDialogVisible.value = true;
        }

        async function submitProcess() {
            if (!processForm.can_return || !processForm.action_type) {
                ElementPlus.ElMessage.warning('请选择退货决策和处置动作');
                return;
            }
            submitting.value = true;
            try {
                const res = await api('/api/slow-moving/process', 'POST', {
                    sku_id: processForm.sku_id,
                    can_return: processForm.can_return,
                    return_reason: processForm.return_reason,
                    action_type: processForm.action_type,
                    action_detail: processForm.action_detail,
                    action_deadline: processForm.action_deadline,
                    operator: '采购主管',
                });
                if (res.code === 0) {
                    ElementPlus.ElMessage.success('处理成功');
                    processDialogVisible.value = false;
                    loadSlowList();
                    loadDashboard();
                }
            } catch (e) {}
            submitting.value = false;
        }

        // 完成弹窗
        function openCompleteDialog(row) {
            Object.assign(completeForm, {
                sku_id: row.id, sku_code: row.sku_code,
                actual_return_amount: 0, actual_clear_amount: 0, result_note: '',
            });
            completeDialogVisible.value = true;
        }

        async function submitComplete() {
            submitting.value = true;
            try {
                const res = await api('/api/slow-moving/complete', 'POST', {
                    sku_id: completeForm.sku_id,
                    actual_return_amount: completeForm.actual_return_amount,
                    actual_clear_amount: completeForm.actual_clear_amount,
                    result_note: completeForm.result_note,
                    operator: '采购主管',
                });
                if (res.code === 0) {
                    ElementPlus.ElMessage.success('已标记完成');
                    completeDialogVisible.value = false;
                    loadSlowList();
                    loadDashboard();
                }
            } catch (e) {}
            submitting.value = false;
        }

        // 批量处理
        async function batchProcess(canReturn, actionType) {
            const ids = selectedRows.value.map(r => r.id);
            try {
                const res = await api('/api/slow-moving/batch-process', 'POST', {
                    sku_ids: ids,
                    can_return: canReturn,
                    action_type: actionType,
                    operator: '采购主管',
                });
                if (res.code === 0) {
                    const success = res.data.filter(r => r.success).length;
                    ElementPlus.ElMessage.success(`批量处理完成: ${success}/${ids.length}`);
                    loadSlowList();
                    loadDashboard();
                }
            } catch (e) {}
        }

        // 查看日志
        async function viewLogs(row) {
            try {
                const res = await api('/api/slow-moving/logs', 'GET', {
                    sku_id: row.id, page_size: 50
                });
                if (res.code === 0) {
                    logList.value = res.data.items;
                    logDialogVisible.value = true;
                }
            } catch (e) {
                logList.value = [];
                logDialogVisible.value = true;
            }
        }

        // 渲染图表
        function renderCharts() {
            nextTick(() => {
                // 处理进度饼图
                const progressEl = document.getElementById('chart-progress');
                if (progressEl) {
                    const chart = echarts.init(progressEl);
                    chart.setOption({
                        tooltip: { trigger: 'item' },
                        series: [{
                            type: 'pie', radius: ['45%', '70%'],
                            label: { show: true, formatter: '{b}: {c}' },
                            data: [
                                { value: dashboardData.completed, name: '已完成', itemStyle: { color: '#10b981' } },
                                { value: dashboardData.processing, name: '处理中', itemStyle: { color: '#3b82f6' } },
                                { value: dashboardData.pending, name: '待处理', itemStyle: { color: '#f59e0b' } },
                            ]
                        }]
                    });
                }

                // 退货决策分布
                const returnEl = document.getElementById('chart-return');
                if (returnEl) {
                    const chart = echarts.init(returnEl);
                    const stats = dashboardData.can_return_stats || {};
                    chart.setOption({
                        tooltip: { trigger: 'item' },
                        series: [{
                            type: 'pie', radius: '65%',
                            data: [
                                { value: stats['yes'] || 0, name: '能退', itemStyle: { color: '#10b981' } },
                                { value: stats['no'] || 0, name: '不能退', itemStyle: { color: '#ef4444' } },
                                { value: stats['partial'] || 0, name: '部分可退', itemStyle: { color: '#f59e0b' } },
                            ]
                        }]
                    });
                }

                // 处置动作分布
                const actionEl = document.getElementById('chart-action');
                if (actionEl) {
                    const chart = echarts.init(actionEl);
                    const stats = dashboardData.action_stats || {};
                    const labels = {
                        'return': '退货', 'discount': '打折', 'bundle': '搭配',
                        'transfer': '调拨', 'write_off': '报损', 'hold': '暂不处理'
                    };
                    chart.setOption({
                        tooltip: { trigger: 'axis' },
                        xAxis: {
                            type: 'category',
                            data: Object.keys(stats).map(k => labels[k] || k),
                        },
                        yAxis: { type: 'value' },
                        series: [{
                            type: 'bar', data: Object.values(stats),
                            itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
                        }]
                    });
                }
            });
        }

        // 辅助方法
        function handleMenuSelect(index) {
            activeMenu.value = index;
            if (index === 'dashboard') loadDashboard();
            if (index === 'slow-list') loadSlowList();
            if (index === 'slow-dashboard') {
                loadDashboard();
                setTimeout(renderCharts, 300);
            }
        }

        function handleSelectionChange(rows) { selectedRows.value = rows; }
        function handlePageChange(page) { filterForm.page = page; loadSlowList(); }
        function handleSizeChange(size) { filterForm.page_size = size; filterForm.page = 1; loadSlowList(); }
        function resetFilter() {
            Object.assign(filterForm, {
                status: '', can_return: '', action_type: '',
                keyword: '', page: 1, page_size: 20,
            });
            loadSlowList();
        }

        function formatMoney(val) {
            if (!val && val !== 0) return '0';
            return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        }

        function statusType(s) {
            return { 'pending': 'warning', 'processing': '', 'completed': 'success' }[s] || 'info';
        }
        function statusLabel(s) {
            return { 'pending': '待处理', 'processing': '处理中', 'completed': '已完成' }[s] || s;
        }
        function returnType(r) {
            return { 'yes': 'success', 'no': 'danger', 'partial': 'warning' }[r] || 'info';
        }
        function returnLabel(r) {
            return { 'yes': '能退', 'no': '不能退', 'partial': '部分可退' }[r] || r;
        }
        function actionLabel(a) {
            return {
                'return': '退货', 'discount': '打折清仓', 'bundle': '搭配销售',
                'transfer': '调拨', 'write_off': '报损', 'hold': '暂不处理'
            }[a] || a;
        }

        async function calculateKPI() {
            ElementPlus.ElMessage.info('KPI计算功能将在数据同步后自动执行');
        }
        async function saveKPI() {}

        // ==================== 初始化 ====================
        onMounted(() => {
            loadDashboard();
        });

        return {
            // 状态
            activeMenu, loading, submitting, currentPeriod, zhCn,
            dashboardData, slowList, slowTotal, selectedRows, filterForm,
            processDialogVisible, processForm,
            completeDialogVisible, completeForm,
            logDialogVisible, logList,
            kpiData, commissionData,
            // 计算属性
            pageTitle, systemHealthType, completionCardClass, impactData,
            // 方法
            handleMenuSelect, loadSlowList, resetFilter,
            handleSelectionChange, handlePageChange, handleSizeChange,
            openProcessDialog, submitProcess,
            openCompleteDialog, submitComplete,
            batchProcess, viewLogs,
            formatMoney, statusType, statusLabel, returnType, returnLabel, actionLabel,
            calculateKPI, saveKPI,
        };
    }
});

app.use(ElementPlus);
app.mount('#app');
