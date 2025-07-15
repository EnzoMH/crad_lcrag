/**
 * AI 에이전트 시스템 대시보드 JavaScript
 *
 * Features:
 * - 실시간 데이터 업데이트
 * - 성능 차트 표시
 * - 에이전트 관리
 * - 작업 모니터링
 */

class AgentDashboard {
  constructor() {
    this.refreshInterval = 30000; // 30초
    this.performanceChart = null;
    this.refreshTimer = null;

    this.init();
  }

  async init() {
    this.setupEventListeners();
    this.initPerformanceChart();
    await this.loadDashboardData();
    this.startAutoRefresh();

    console.log("AI 에이전트 대시보드 초기화 완료");
  }

  setupEventListeners() {
    // 새로고침 버튼
    document.getElementById("refresh-btn").addEventListener("click", () => {
      this.loadDashboardData();
    });

    // 에이전트 생성 버튼
    document
      .getElementById("create-agent-btn")
      .addEventListener("click", () => {
        this.showAgentModal();
      });

    // 모달 닫기
    document.getElementById("close-modal-btn").addEventListener("click", () => {
      this.hideAgentModal();
    });

    document.getElementById("cancel-btn").addEventListener("click", () => {
      this.hideAgentModal();
    });

    // 에이전트 폼 제출
    document.getElementById("agent-form").addEventListener("submit", (e) => {
      e.preventDefault();
      this.createAgent();
    });

    // 성능 차트 시간대 변경
    document
      .getElementById("performance-timeframe")
      .addEventListener("change", (e) => {
        this.updatePerformanceChart(e.target.value);
      });

    // 빠른 작업 버튼들
    document
      .getElementById("start-crawling-btn")
      .addEventListener("click", () => {
        this.startCrawling();
      });

    document
      .getElementById("analyze-data-btn")
      .addEventListener("click", () => {
        this.analyzeData();
      });

    document
      .getElementById("optimize-system-btn")
      .addEventListener("click", () => {
        this.optimizeSystem();
      });

    document
      .getElementById("view-monitoring-btn")
      .addEventListener("click", () => {
        window.open("/monitoring", "_blank");
      });

    // 알림 토스트 닫기
    document.getElementById("close-toast").addEventListener("click", () => {
      this.hideToast();
    });

    // 모달 외부 클릭 시 닫기
    document.getElementById("agent-modal").addEventListener("click", (e) => {
      if (e.target.id === "agent-modal") {
        this.hideAgentModal();
      }
    });
  }

  async loadDashboardData() {
    try {
      this.showLoading();

      // 병렬로 데이터 로드
      const [systemInfo, agentsList, queueStatus] = await Promise.all([
        this.fetchSystemInfo(),
        this.fetchAgentsList(),
        this.fetchQueueStatus(),
      ]);

      this.updateQuickStats(systemInfo, queueStatus);
      this.updateAgentsList(agentsList);
      this.updateSystemStatus(systemInfo);

      await this.loadRecentTasks();
    } catch (error) {
      console.error("대시보드 데이터 로드 오류:", error);
      this.showToast("데이터 로드 중 오류가 발생했습니다", "error");
    } finally {
      this.hideLoading();
    }
  }

  async fetchSystemInfo() {
    const response = await fetch("/system/info");
    if (!response.ok) throw new Error("시스템 정보 조회 실패");
    return await response.json();
  }

  async fetchAgentsList() {
    const response = await fetch("/api/agents/");
    if (!response.ok) throw new Error("에이전트 목록 조회 실패");
    return await response.json();
  }

  async fetchQueueStatus() {
    const response = await fetch("/api/agents/queue/status");
    if (!response.ok) {
      // 큐 상태를 가져올 수 없는 경우 기본값 반환
      return { pending_tasks: 0, running_tasks: 0, completed_tasks: 0 };
    }
    return await response.json();
  }

  async loadRecentTasks() {
    try {
      // 최근 작업 목록을 가져오는 API가 구현되면 사용
      // 현재는 mock 데이터 표시
      this.updateRecentTasks([
        {
          id: "task_001",
          agent_name: "검색 전략 에이전트",
          task_type: "데이터 검색",
          status: "completed",
          created_at: new Date(Date.now() - 300000).toISOString(),
          execution_time: 2.5,
        },
        {
          id: "task_002",
          agent_name: "연락처 에이전트",
          task_type: "연락처 추출",
          status: "running",
          created_at: new Date(Date.now() - 60000).toISOString(),
        },
        {
          id: "task_003",
          agent_name: "검증 에이전트",
          task_type: "데이터 검증",
          status: "completed",
          created_at: new Date(Date.now() - 600000).toISOString(),
          execution_time: 1.8,
        },
      ]);
    } catch (error) {
      console.error("최근 작업 로드 오류:", error);
    }
  }

  updateQuickStats(systemInfo, queueStatus) {
    // 총 에이전트 수
    document.getElementById("total-agents").textContent =
      systemInfo.agents?.total_count || 0;

    // 활성 작업 수
    document.getElementById("active-tasks").textContent =
      queueStatus.running_tasks || 0;

    // 성공률
    const successRate =
      systemInfo.performance?.successful_requests &&
      systemInfo.performance?.total_requests
        ? (
            (systemInfo.performance.successful_requests /
              systemInfo.performance.total_requests) *
            100
          ).toFixed(1)
        : 0;
    document.getElementById("success-rate").textContent = `${successRate}%`;

    // 평균 응답 시간
    const avgResponseTime = systemInfo.performance?.average_response_time || 0;
    document.getElementById(
      "avg-response-time"
    ).textContent = `${avgResponseTime.toFixed(1)}s`;
  }

  updateAgentsList(agents) {
    const agentsContainer = document.getElementById("agents-list");

    if (!agents || agents.length === 0) {
      agentsContainer.innerHTML = `
                <div class="text-center text-gray-500 dark:text-gray-400 py-8">
                    <i class="fas fa-robot text-3xl mb-2"></i>
                    <p>등록된 에이전트가 없습니다</p>
                    <p class="text-sm">새 에이전트를 생성해보세요</p>
                </div>
            `;
      return;
    }

    agentsContainer.innerHTML = agents
      .map(
        (agent) => `
            <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center">
                            <span class="status-indicator ${this.getStatusClass(
                              agent.status
                            )}"></span>
                            <h4 class="font-medium text-gray-900 dark:text-white">${
                              agent.name
                            }</h4>
                        </div>
                        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">${
                          agent.type
                        }</p>
                        <div class="flex items-center mt-2 text-xs text-gray-500 dark:text-gray-400">
                            <span>작업: ${
                              agent.metrics?.total_tasks || 0
                            }</span>
                            <span class="mx-2">•</span>
                            <span>성공률: ${(
                              agent.metrics?.success_rate || 0
                            ).toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="flex space-x-2">
                        <button onclick="dashboard.viewAgentDetails('${
                          agent.id
                        }')" 
                                class="text-blue-600 hover:text-blue-800" title="상세보기">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button onclick="dashboard.deleteAgent('${agent.id}')" 
                                class="text-red-600 hover:text-red-800" title="삭제">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `
      )
      .join("");
  }

  updateRecentTasks(tasks) {
    const tasksContainer = document.getElementById("recent-tasks");

    if (!tasks || tasks.length === 0) {
      tasksContainer.innerHTML = `
                <div class="text-center text-gray-500 dark:text-gray-400 py-8">
                    <i class="fas fa-tasks text-3xl mb-2"></i>
                    <p>최근 작업이 없습니다</p>
                </div>
            `;
      return;
    }

    tasksContainer.innerHTML = tasks
      .map(
        (task) => `
            <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center">
                            <span class="status-indicator ${this.getStatusClass(
                              task.status
                            )}"></span>
                            <h4 class="font-medium text-gray-900 dark:text-white">${
                              task.task_type
                            }</h4>
                        </div>
                        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">${
                          task.agent_name
                        }</p>
                        <div class="flex items-center mt-2 text-xs text-gray-500 dark:text-gray-400">
                            <span>${this.formatTime(task.created_at)}</span>
                            ${
                              task.execution_time
                                ? `<span class="mx-2">•</span><span>${task.execution_time}초</span>`
                                : ""
                            }
                        </div>
                    </div>
                    <div class="flex items-center">
                        <span class="px-2 py-1 text-xs rounded-full ${this.getStatusBadgeClass(
                          task.status
                        )}">
                            ${this.getStatusText(task.status)}
                        </span>
                    </div>
                </div>
            </div>
        `
      )
      .join("");
  }

  updateSystemStatus(systemInfo) {
    const statusElement = document.getElementById("system-status");
    const isHealthy = systemInfo.status === "running";

    statusElement.className = `status-indicator ${
      isHealthy ? "status-healthy" : "status-warning"
    }`;
  }

  initPerformanceChart() {
    const ctx = document.getElementById("performance-chart").getContext("2d");

    this.performanceChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "CPU 사용률 (%)",
            data: [],
            borderColor: "rgb(59, 130, 246)",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            tension: 0.1,
          },
          {
            label: "메모리 사용률 (%)",
            data: [],
            borderColor: "rgb(16, 185, 129)",
            backgroundColor: "rgba(16, 185, 129, 0.1)",
            tension: 0.1,
          },
          {
            label: "응답 시간 (ms)",
            data: [],
            borderColor: "rgb(245, 158, 11)",
            backgroundColor: "rgba(245, 158, 11, 0.1)",
            tension: 0.1,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            type: "linear",
            display: true,
            position: "left",
            max: 100,
          },
          y1: {
            type: "linear",
            display: true,
            position: "right",
            grid: {
              drawOnChartArea: false,
            },
          },
        },
        plugins: {
          legend: {
            display: true,
            position: "top",
          },
        },
      },
    });

    // 초기 차트 데이터 로드
    this.updatePerformanceChart("24h");
  }

  async updatePerformanceChart(timeframe) {
    try {
      // Mock 데이터 생성 (실제로는 API에서 가져옴)
      const hours = timeframe === "1h" ? 1 : timeframe === "6h" ? 6 : 24;
      const dataPoints = Math.min(hours * 4, 48); // 15분 간격, 최대 48포인트

      const labels = [];
      const cpuData = [];
      const memoryData = [];
      const responseTimeData = [];

      for (let i = dataPoints - 1; i >= 0; i--) {
        const time = new Date(Date.now() - i * 15 * 60 * 1000);
        labels.push(
          time.toLocaleTimeString("ko-KR", {
            hour: "2-digit",
            minute: "2-digit",
          })
        );

        // Mock 데이터 생성
        cpuData.push(30 + Math.random() * 40);
        memoryData.push(40 + Math.random() * 30);
        responseTimeData.push(100 + Math.random() * 200);
      }

      this.performanceChart.data.labels = labels;
      this.performanceChart.data.datasets[0].data = cpuData;
      this.performanceChart.data.datasets[1].data = memoryData;
      this.performanceChart.data.datasets[2].data = responseTimeData;
      this.performanceChart.update();
    } catch (error) {
      console.error("성능 차트 업데이트 오류:", error);
    }
  }

  // 에이전트 관리 메서드들
  showAgentModal() {
    document.getElementById("agent-modal").classList.remove("hidden");
    document.getElementById("agent-name").focus();
  }

  hideAgentModal() {
    document.getElementById("agent-modal").classList.add("hidden");
    document.getElementById("agent-form").reset();
  }

  async createAgent() {
    try {
      const formData = {
        name: document.getElementById("agent-name").value,
        type: document.getElementById("agent-type").value,
        description: document.getElementById("agent-description").value,
      };

      const response = await fetch("/api/agents/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error("에이전트 생성 실패");
      }

      const result = await response.json();

      this.hideAgentModal();
      this.showToast("에이전트가 성공적으로 생성되었습니다", "success");
      this.loadDashboardData(); // 데이터 새로고침
    } catch (error) {
      console.error("에이전트 생성 오류:", error);
      this.showToast("에이전트 생성 중 오류가 발생했습니다", "error");
    }
  }

  async deleteAgent(agentId) {
    if (!confirm("정말로 이 에이전트를 삭제하시겠습니까?")) {
      return;
    }

    try {
      const response = await fetch(`/api/agents/${agentId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("에이전트 삭제 실패");
      }

      this.showToast("에이전트가 삭제되었습니다", "success");
      this.loadDashboardData(); // 데이터 새로고침
    } catch (error) {
      console.error("에이전트 삭제 오류:", error);
      this.showToast("에이전트 삭제 중 오류가 발생했습니다", "error");
    }
  }

  viewAgentDetails(agentId) {
    // 에이전트 상세 페이지로 이동하거나 모달 표시
    window.open(`/agents/${agentId}`, "_blank");
  }

  // 빠른 작업 메서드들
  async startCrawling() {
    try {
      this.showToast("크롤링 작업을 시작합니다...", "info");

      const response = await fetch("/api/crawling/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: "빠른 크롤링 작업",
          targets: [{ name: "샘플 교회", category: "교회", region: "서울" }],
          strategy: "balanced",
        }),
      });

      if (!response.ok) {
        throw new Error("크롤링 시작 실패");
      }

      const result = await response.json();
      this.showToast("크롤링 작업이 시작되었습니다", "success");
    } catch (error) {
      console.error("크롤링 시작 오류:", error);
      this.showToast("크롤링 시작 중 오류가 발생했습니다", "error");
    }
  }

  async analyzeData() {
    this.showToast("데이터 분석을 시작합니다...", "info");
    // 실제 분석 로직 구현
  }

  async optimizeSystem() {
    this.showToast("시스템 최적화를 시작합니다...", "info");
    // 실제 최적화 로직 구현
  }

  // 유틸리티 메서드들
  getStatusClass(status) {
    switch (status?.toLowerCase()) {
      case "running":
      case "active":
      case "completed":
        return "status-healthy";
      case "warning":
      case "pending":
        return "status-warning";
      case "error":
      case "failed":
        return "status-error";
      default:
        return "status-warning";
    }
  }

  getStatusBadgeClass(status) {
    switch (status?.toLowerCase()) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "running":
        return "bg-blue-100 text-blue-800";
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  }

  getStatusText(status) {
    switch (status?.toLowerCase()) {
      case "completed":
        return "완료";
      case "running":
        return "실행중";
      case "pending":
        return "대기중";
      case "failed":
        return "실패";
      default:
        return "알 수 없음";
    }
  }

  formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) {
      // 1분 미만
      return "방금 전";
    } else if (diff < 3600000) {
      // 1시간 미만
      return `${Math.floor(diff / 60000)}분 전`;
    } else if (diff < 86400000) {
      // 24시간 미만
      return `${Math.floor(diff / 3600000)}시간 전`;
    } else {
      return date.toLocaleDateString("ko-KR");
    }
  }

  showToast(message, type = "info") {
    const toast = document.getElementById("notification-toast");
    const messageElement = document.getElementById("toast-message");

    messageElement.textContent = message;

    // 토스트 색상 설정
    toast.className = toast.className.replace(/bg-\w+-500/, "");
    switch (type) {
      case "success":
        toast.classList.add("bg-green-500");
        break;
      case "error":
        toast.classList.add("bg-red-500");
        break;
      case "warning":
        toast.classList.add("bg-yellow-500");
        break;
      default:
        toast.classList.add("bg-blue-500");
    }

    // 토스트 표시
    toast.classList.remove("translate-x-full");

    // 3초 후 자동으로 숨김
    setTimeout(() => {
      this.hideToast();
    }, 3000);
  }

  hideToast() {
    const toast = document.getElementById("notification-toast");
    toast.classList.add("translate-x-full");
  }

  showLoading() {
    document.body.classList.add("loading");
  }

  hideLoading() {
    document.body.classList.remove("loading");
  }

  startAutoRefresh() {
    this.refreshTimer = setInterval(() => {
      this.loadDashboardData();
    }, this.refreshInterval);
  }

  stopAutoRefresh() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
}

// 대시보드 인스턴스 생성 및 전역 변수 설정
let dashboard;

document.addEventListener("DOMContentLoaded", () => {
  dashboard = new AgentDashboard();
});

// 페이지 언로드 시 정리
window.addEventListener("beforeunload", () => {
  if (dashboard) {
    dashboard.stopAutoRefresh();
  }
});
