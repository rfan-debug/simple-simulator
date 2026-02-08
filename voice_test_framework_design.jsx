import { useState } from "react";

const LAYERS = [
  {
    id: "scenario",
    name: "🎬 Scenario Engine",
    subtitle: "测试场景编排层",
    color: "#E8D5B7",
    borderColor: "#C4A882",
    textColor: "#5C4A2E",
    modules: [
      {
        name: "YAML/DSL 场景定义",
        desc: "声明式定义多轮对话场景、分支逻辑、时间线",
        code: `# scenario: hotel_booking_noisy.yaml
scenario:
  name: "嘈杂环境酒店预订"
  environment:
    noise_profile: "cafe_ambient"
    noise_snr_db: 15
    network: { latency_ms: 80, jitter_ms: 20 }
  
  timeline:
    - at: 0s
      action: user_speak
      audio: "tts://你好，我想预订一间房间"
      
    - at: 2.5s
      action: inject_noise
      type: "transient"
      source: "phone_ring.wav"
      
    - at: 3s
      action: assert_system
      expect:
        intent: "hotel_booking"
        did_not: "ask_repeat"  # 噪音下仍能理解
        
    - at: 4s
      action: user_speak
      audio: "tts://下周五入住，住两晚"
      speech_style:
        speed: 1.3        # 语速偏快
        interruption: true # 在系统说话时插入

    - at: 6s
      action: expect_tool_call
      tool: "check_availability"
      args_contain: { checkin: "next_friday", nights: 2 }
      timeout_ms: 3000`,
      },
      {
        name: "场景编排器 (Orchestrator)",
        desc: "按时间线驱动所有模拟层，支持条件分支和循环",
        code: `class ScenarioOrchestrator:
    """
    核心调度器：按时间线驱动所有 simulation layer
    支持条件分支、并行事件、动态响应
    """
    def __init__(self, scenario_path: str):
        self.scenario = load_yaml(scenario_path)
        self.timeline = PriorityQueue()  # 事件优先队列
        self.clock = SimulatedClock()
        self.layers = {}  # 注册的模拟层
        
    def register_layer(self, name: str, layer: SimulationLayer):
        self.layers[name] = layer
        
    async def run(self, system_under_test: VoiceSystem):
        """执行完整测试场景"""
        self._load_timeline(self.scenario["timeline"])
        results = TestResults()
        
        while not self.timeline.empty():
            event = self.timeline.get()
            await self.clock.advance_to(event.timestamp)
            
            match event.action:
                case "user_speak":
                    audio = await self.layers["audio"].generate(
                        text=event.get("audio"),
                        style=event.get("speech_style", {})
                    )
                    await system_under_test.push_audio(audio)
                    
                case "inject_noise":
                    await self.layers["environment"].inject(
                        noise_type=event["type"],
                        source=event.get("source")
                    )
                    
                case "inject_video":
                    frame = await self.layers["video"].generate(event)
                    await system_under_test.push_video(frame)
                    
                case "assert_system":
                    result = await self._evaluate(
                        system_under_test, event["expect"]
                    )
                    results.add(event.timestamp, result)
                    
                case "expect_tool_call":
                    result = await self.layers["tools"].wait_for_call(
                        tool_name=event["tool"],
                        expected_args=event.get("args_contain"),
                        timeout=event.get("timeout_ms", 5000)
                    )
                    results.add(event.timestamp, result)
                    
                case "conditional":
                    # 根据系统响应动态插入新事件
                    branch = self._eval_condition(event["condition"])
                    self._load_timeline(event["branches"][branch])
                    
        return results`,
      },
    ],
  },
  {
    id: "input",
    name: "🎤 Input Simulation Layer",
    subtitle: "多模态输入模拟层",
    color: "#D5E8D4",
    borderColor: "#82B366",
    textColor: "#2D5016",
    modules: [
      {
        name: "Audio Stream 模拟器",
        desc: "TTS合成 + 语音风格控制 + 真人录音混合 + 流式分块推送",
        code: `class AudioStreamSimulator(SimulationLayer):
    """
    模拟真实麦克风输入流
    - 支持 TTS 合成和预录音频
    - 模拟真实语音特征：语速、停顿、口头禅、口音
    - 流式分块推送，模拟真实采样率
    """
    def __init__(self, config: AudioConfig):
        self.sample_rate = config.sample_rate  # 16000
        self.chunk_duration_ms = config.chunk_ms  # 20ms
        self.tts_engine = TTSEngine(config.tts_provider)
        self.voice_bank = VoiceBank(config.voice_profiles)
        
    async def generate(self, text: str = None, 
                       audio_file: str = None,
                       style: dict = None) -> AsyncIterator[AudioChunk]:
        """生成音频流"""
        if text and text.startswith("tts://"):
            raw_audio = await self.tts_engine.synthesize(
                text=text[6:],
                voice=style.get("voice", "default"),
                speed=style.get("speed", 1.0),
                emotion=style.get("emotion", "neutral"),
            )
        elif audio_file:
            raw_audio = load_audio(audio_file)
        
        # 添加真实语音特征
        if style:
            raw_audio = self._apply_speech_style(raw_audio, style)
            
        # 流式分块推送（模拟真实麦克风采样）
        chunk_size = int(self.sample_rate * self.chunk_duration_ms / 1000)
        for i in range(0, len(raw_audio), chunk_size):
            chunk = raw_audio[i:i + chunk_size]
            yield AudioChunk(
                data=chunk,
                timestamp=self.clock.now(),
                sample_rate=self.sample_rate
            )
            await asyncio.sleep(self.chunk_duration_ms / 1000)
            
    def _apply_speech_style(self, audio, style):
        """模拟真实语音特征"""
        if style.get("hesitation"):
            audio = insert_fillers(audio, ["嗯", "那个", "就是"])
        if style.get("stutter"):
            audio = add_repetition(audio, probability=0.1)
        if style.get("accent"):
            audio = apply_accent_transfer(audio, style["accent"])
        if style.get("interruption"):
            audio = trim_leading_silence(audio, max_ms=50)
        return audio`,
      },
      {
        name: "Video/Screen 模拟器",
        desc: "模拟相机画面、屏幕共享、文档展示等视觉输入",
        code: `class VideoStreamSimulator(SimulationLayer):
    """
    模拟视觉输入通道
    - 相机画面：人脸、手势、环境
    - 屏幕共享：应用界面、文档、网页
    - 物理物体：产品、文档扫描、白板
    """
    def __init__(self, config: VideoConfig):
        self.fps = config.fps  # 30
        self.resolution = config.resolution  # (1280, 720)
        self.generators = {
            "camera": CameraSimGenerator(),
            "screen": ScreenShareGenerator(), 
            "document": DocumentScanGenerator(),
        }
        
    async def generate(self, event: dict) -> AsyncIterator[VideoFrame]:
        match event["source"]:
            case "camera":
                # 模拟相机画面
                frames = self.generators["camera"].render(
                    scene=event.get("scene", "office_desk"),
                    face_expression=event.get("expression"),
                    gesture=event.get("gesture"),  # pointing, waving
                    objects_in_view=event.get("objects", []),
                    lighting=event.get("lighting", "normal"),
                )
            case "screen":
                # 模拟屏幕共享
                frames = self.generators["screen"].render(
                    app=event["app"],  # "browser", "excel", "terminal"
                    content=event["content"],
                    cursor_path=event.get("cursor_path"),
                    highlight_region=event.get("highlight"),
                )
            case "image_file":
                # 直接使用图片文件
                frames = static_frames(
                    load_image(event["path"]),
                    duration_s=event.get("duration", 3)
                )
                
        for frame in frames:
            yield VideoFrame(
                data=frame,
                timestamp=self.clock.now(),
                resolution=self.resolution
            )
            await asyncio.sleep(1.0 / self.fps)
            
    # 组合场景示例：用户指着屏幕上的错误问AI
    # timeline:
    #   - at: 0s
    #     action: inject_video
    #     source: screen
    #     app: terminal
    #     content: "$ python app.py\\nTraceback: IndexError..."
    #   - at: 0.5s
    #     action: user_speak  
    #     audio: "tts://你看这个报错，怎么修？"`,
      },
      {
        name: "Barge-in / 打断模拟",
        desc: "模拟用户在系统说话过程中插话的真实交互模式",
        code: `class BargeInSimulator:
    """
    模拟真实的打断/插话行为
    这是语音对话中最关键也最难测试的场景之一
    """
    PATTERNS = {
        "eager_interrupt": {
            # 用户在系统说到关键词后立即打断
            "trigger": "keyword_detected",
            "delay_ms": (100, 300),
            "overlap_duration_ms": (500, 2000),
        },
        "correction": {
            # 系统说错了，用户打断纠正
            "trigger": "incorrect_info",
            "delay_ms": (200, 500),
            "user_says": "不对不对，我说的是{correction}",
        },
        "impatient": {
            # 系统回复太长，用户不耐烦打断
            "trigger": "response_duration > 5s",
            "delay_ms": (0, 100),
            "user_says": "好了好了我知道了，直接告诉我{question}",
        },
        "backchannel": {
            # 不算真正打断，只是嗯嗯啊啊表示在听
            "trigger": "periodic",
            "interval_ms": (2000, 4000),
            "audio": ["嗯", "对", "好的", "嗯嗯"],
            "is_true_interrupt": False,
        },
    }
    
    async def simulate(self, pattern: str, 
                       system_audio_stream,
                       user_audio_gen) -> InterruptEvent:
        config = self.PATTERNS[pattern]
        
        # 等待触发条件
        await self._wait_trigger(config["trigger"], system_audio_stream)
        
        # 随机延迟（模拟人类反应时间）
        delay = random.uniform(*config["delay_ms"]) / 1000
        await asyncio.sleep(delay)
        
        # 生成打断音频并推送
        interrupt_audio = await user_audio_gen.generate(
            text=config.get("user_says", ""),
        )
        
        return InterruptEvent(
            audio=interrupt_audio,
            is_true_interrupt=config.get("is_true_interrupt", True),
            timestamp=self.clock.now(),
        )`,
      },
    ],
  },
  {
    id: "environment",
    name: "🌍 Environment Simulation",
    subtitle: "物理环境与网络模拟层",
    color: "#DAE8FC",
    borderColor: "#6C8EBF",
    textColor: "#1A3A5C",
    modules: [
      {
        name: "噪音引擎",
        desc: "多层噪音混合：环境底噪 + 瞬态事件 + 多人说话",
        code: `class NoiseEngine(SimulationLayer):
    """
    真实环境噪音模拟
    三层噪音模型：
    1. Ambient: 持续环境底噪（咖啡馆、办公室、街道）
    2. Transient: 瞬态噪音事件（门铃、电话铃、狗叫）
    3. Competing Speech: 背景中其他人说话
    """
    AMBIENT_PROFILES = {
        "quiet_room":    {"snr_db": 40, "source": "white_noise_low.wav"},
        "office":        {"snr_db": 25, "source": "office_ambient.wav"},
        "cafe":          {"snr_db": 15, "source": "cafe_crowd.wav"},
        "street":        {"snr_db": 10, "source": "traffic_urban.wav"},
        "construction":  {"snr_db": 5,  "source": "construction.wav"},
        "car_driving":   {"snr_db": 18, "source": "car_interior.wav"},
    }
    
    TRANSIENT_EVENTS = {
        "phone_ring":    {"duration": (2, 5),  "peak_db": -10},
        "door_knock":    {"duration": (1, 3),  "peak_db": -15},
        "dog_bark":      {"duration": (1, 4),  "peak_db": -8},
        "baby_cry":      {"duration": (3, 10), "peak_db": -5},
        "notification":  {"duration": (0.5, 1),"peak_db": -20},
        "keyboard":      {"duration": (0.2, 1),"peak_db": -25},
        "siren":         {"duration": (5, 15), "peak_db": -3},
    }
    
    def __init__(self, profile: str, snr_override: float = None):
        self.ambient = self._load_ambient(profile, snr_override)
        self.mixer = AudioMixer()
        self.active_transients = []
        
    def mix_with_speech(self, speech_chunk: AudioChunk) -> AudioChunk:
        """将噪音混入语音流"""
        mixed = self.mixer.mix([
            (speech_chunk.data, 0),  # 语音在 0dB
            (self.ambient.next_chunk(), self.ambient.snr_db),
            *[(t.next_chunk(), t.current_db) 
              for t in self.active_transients if t.is_active()],
        ])
        return AudioChunk(data=mixed, timestamp=speech_chunk.timestamp)
        
    async def inject(self, noise_type: str, source: str = None):
        """注入瞬态噪音事件"""
        if noise_type == "transient":
            config = self.TRANSIENT_EVENTS[source]
            event = TransientNoise(
                source=source,
                duration=random.uniform(*config["duration"]),
                peak_db=config["peak_db"],
            )
            self.active_transients.append(event)
        elif noise_type == "competing_speech":
            # 背景中有另一个人在说话
            bg_speech = await self.tts.synthesize(
                text=source, voice="background_speaker"
            )
            self.active_transients.append(
                CompetingSpeech(audio=bg_speech, snr_db=-10)
            )`,
      },
      {
        name: "网络状况模拟",
        desc: "延迟、抖动、丢包、断线重连等网络异常",
        code: `class NetworkSimulator:
    """
    模拟真实网络状况对语音流的影响
    """
    PROFILES = {
        "perfect":  {"latency": 10,  "jitter": 2,  "loss": 0},
        "good_4g":  {"latency": 50,  "jitter": 15, "loss": 0.01},
        "poor_4g":  {"latency": 150, "jitter": 50, "loss": 0.05},
        "bad_wifi": {"latency": 200, "jitter": 100,"loss": 0.10},
        "elevator": {"latency": 500, "jitter": 200,"loss": 0.30},
    }
    
    async def apply(self, chunk: AudioChunk) -> AudioChunk | None:
        # 模拟丢包
        if random.random() < self.loss_rate:
            return None  # 丢失此包
            
        # 模拟延迟 + 抖动
        delay = self.base_latency + random.gauss(0, self.jitter)
        await asyncio.sleep(max(0, delay) / 1000)
        
        # 模拟带宽限制导致的音频降质
        if self.bandwidth_limit:
            chunk = self._compress_audio(chunk, self.bandwidth_limit)
            
        return chunk
        
    async def simulate_disconnect(self, duration_s: float):
        """模拟网络断线"""
        self.is_connected = False
        await asyncio.sleep(duration_s)
        self.is_connected = True
        # 断线重连后可能有音频缓冲堆积
        self._flush_buffer()`,
      },
      {
        name: "物理世界交互模拟",
        desc: "模拟用户与物理世界的互动对对话的影响",
        code: `class PhysicalWorldSimulator(SimulationLayer):
    """
    模拟真实物理世界中会发生的事情
    这些事件会影响语音对话的质量和流程
    """
    SCENARIOS = {
        "multitasking": {
            # 用户一边打电话一边做其他事
            "events": [
                {"type": "typing", "affects": "background_noise"},
                {"type": "walking", "affects": "mic_movement"},
                {"type": "driving", "affects": "ambient_noise_change"},
            ]
        },
        "device_events": {
            # 设备相关事件
            "events": [
                {"type": "switch_to_speaker", 
                 "affects": "audio_quality_change",
                 "echo_introduced": True},
                {"type": "bluetooth_switch",
                 "affects": "brief_audio_gap",
                 "gap_ms": 500},
                {"type": "notification_sound",
                 "affects": "transient_noise"},
                {"type": "app_switch",
                 "affects": "screen_content_change"},
            ]
        },
        "environment_change": {
            # 环境变化
            "events": [
                {"type": "enter_room",
                 "transition": ("street", "quiet_room"),
                 "transition_duration_s": 3},
                {"type": "someone_enters",
                 "introduces": "competing_speech"},
                {"type": "door_closes",
                 "noise_profile_change": "more_isolated"},
            ]
        },
    }
    
    async def simulate_scenario(self, scenario_name, 
                                 audio_sim, noise_engine):
        scenario = self.SCENARIOS[scenario_name]
        for event in scenario["events"]:
            match event["affects"]:
                case "audio_quality_change":
                    # 切换到扬声器 → 引入回声
                    audio_sim.enable_echo(
                        delay_ms=150, decay=0.3
                    )
                case "brief_audio_gap":
                    await audio_sim.pause(event["gap_ms"])
                case "ambient_noise_change":
                    noise_engine.crossfade_profile(
                        *event["transition"],
                        duration=event["transition_duration_s"]
                    )`,
      },
    ],
  },
  {
    id: "tools",
    name: "🔧 Tool Use Simulation",
    subtitle: "工具调用与外部系统模拟层",
    color: "#FFF2CC",
    borderColor: "#D6B656",
    textColor: "#5C4A00",
    modules: [
      {
        name: "Mock Tool Registry",
        desc: "模拟各种工具的响应，支持延迟、失败、部分成功等",
        code: `class MockToolRegistry:
    """
    模拟语音系统可能调用的所有外部工具
    关键：不仅模拟成功，还要模拟各种失败场景
    """
    def __init__(self):
        self.tools = {}
        self.call_log = []  # 记录所有调用用于断言
        
    def register(self, name: str, handler: Callable,
                 latency_ms: tuple = (100, 500),
                 failure_rate: float = 0.0):
        self.tools[name] = ToolMock(
            handler=handler,
            latency=latency_ms,
            failure_rate=failure_rate,
        )
        
    async def handle_call(self, tool_name: str, 
                          args: dict) -> ToolResult:
        self.call_log.append({
            "tool": tool_name, "args": args,
            "timestamp": self.clock.now()
        })
        
        mock = self.tools[tool_name]
        
        # 模拟网络延迟
        latency = random.uniform(*mock.latency) / 1000
        await asyncio.sleep(latency)
        
        # 模拟失败
        if random.random() < mock.failure_rate:
            return ToolResult(
                success=False,
                error="ServiceUnavailable",
                latency_ms=latency * 1000
            )
            
        result = await mock.handler(args)
        return ToolResult(
            success=True, data=result,
            latency_ms=latency * 1000
        )

# 注册示例
registry = MockToolRegistry()

registry.register("check_availability", 
    handler=lambda args: {
        "available": True,
        "rooms": [
            {"type": "标准间", "price": 399},
            {"type": "大床房", "price": 499},
        ]
    },
    latency_ms=(200, 800),
)

registry.register("create_booking",
    handler=lambda args: {
        "booking_id": "BK20240115001",
        "status": "confirmed"
    },
    latency_ms=(500, 2000),  # 下单慢一些
    failure_rate=0.1,         # 10% 失败率
)

# ⚡ 工具调用中的语音特殊场景
registry.register("long_running_search",
    handler=slow_search_handler,
    latency_ms=(3000, 8000),  # 很慢的搜索
    # 测试点：系统是否会说"请稍等，我帮您查一下"
    # 而不是沉默等待？
)`,
      },
      {
        name: "Tool Call 断言器",
        desc: "验证系统是否在正确时机调用了正确的工具",
        code: `class ToolCallAsserter:
    """
    验证工具调用的正确性
    """
    def __init__(self, registry: MockToolRegistry):
        self.registry = registry
        
    def assert_called(self, tool_name: str, 
                      args_contain: dict = None,
                      within_ms: int = 5000):
        """断言某工具被调用，且参数包含预期值"""
        calls = [c for c in self.registry.call_log 
                 if c["tool"] == tool_name]
        assert len(calls) > 0, (
            f"Expected {tool_name} to be called, "
            f"but it wasn't. Calls: {self.registry.call_log}"
        )
        if args_contain:
            last_call = calls[-1]
            for key, value in args_contain.items():
                assert key in last_call["args"], (
                    f"Missing arg '{key}' in {tool_name} call"
                )
                
    def assert_not_called(self, tool_name: str):
        """断言某工具没有被调用"""
        calls = [c for c in self.registry.call_log 
                 if c["tool"] == tool_name]
        assert len(calls) == 0
        
    def assert_call_order(self, *tool_names: str):
        """断言工具调用顺序"""
        actual_order = [c["tool"] for c in self.registry.call_log]
        idx = 0
        for expected in tool_names:
            while idx < len(actual_order):
                if actual_order[idx] == expected:
                    break
                idx += 1
            else:
                raise AssertionError(
                    f"Expected call order {tool_names}, "
                    f"got {actual_order}"
                )
                
    def assert_retry_on_failure(self, tool_name: str,
                                 max_retries: int = 3):
        """断言系统在工具失败后会重试"""
        calls = [c for c in self.registry.call_log 
                 if c["tool"] == tool_name]
        assert len(calls) <= max_retries + 1`,
      },
    ],
  },
  {
    id: "eval",
    name: "📊 Evaluation & Metrics",
    subtitle: "评估与度量层",
    color: "#F8CECC",
    borderColor: "#B85450",
    textColor: "#5C1A1A",
    modules: [
      {
        name: "多维度评估框架",
        desc: "延迟、准确性、自然度、鲁棒性等全方位评估",
        code: `class EvaluationFramework:
    """
    多维度评估系统，每个维度都有独立的评分器
    """
    def __init__(self):
        self.scorers = {
            "latency": LatencyScorer(),
            "accuracy": AccuracyScorer(),
            "naturalness": NaturalnessScorer(),
            "robustness": RobustnessScorer(),
            "tool_use": ToolUseScorer(),
        }
    
    class LatencyScorer:
        """响应延迟评分"""
        THRESHOLDS = {
            "p50_first_byte_ms": 300,   # 首字节延迟
            "p99_first_byte_ms": 1000,
            "turn_taking_gap_ms": 500,  # 轮次切换间隔
            "interrupt_response_ms": 200, # 打断响应时间
            "tool_call_filler_ms": 2000,  # 超过2s应说过渡语
        }
        
        def score(self, results: TestResults) -> dict:
            return {
                "first_byte_p50": percentile(
                    results.first_byte_latencies, 50
                ),
                "turn_gap_avg": mean(results.turn_gaps),
                "filler_appropriateness": self._check_fillers(
                    results
                ),
            }
    
    class RobustnessScorer:
        """鲁棒性评分 - 噪音/网络/打断下的表现"""
        def score(self, clean_results, noisy_results):
            return {
                "noise_degradation": (
                    noisy_results.accuracy 
                    / clean_results.accuracy
                ),  # 越接近1越好
                "packet_loss_resilience": ...,
                "barge_in_handling": ...,
            }
            
    class NaturalnessScorer:
        """
        自然度评分 - 使用 LLM-as-judge
        """
        RUBRIC = \"\"\"
        评估语音对话系统的回复自然度 (1-5分):
        5: 完全像人类对话，语调自然，节奏合适
        4: 基本自然，偶尔有轻微机械感
        3: 能理解但明显是AI，转折生硬
        2: 经常出现不自然的停顿或重复
        1: 机械感严重，对话难以持续
        
        特别关注：
        - 打断后的恢复是否自然
        - 过渡语是否恰当（而非尴尬沉默）
        - 是否能处理口语化表达和不完整句子
        \"\"\"
        
        async def score(self, conversation_log):
            return await llm_judge(
                rubric=self.RUBRIC,
                conversation=conversation_log,
                model="claude-sonnet-4-20250514"
            )`,
      },
      {
        name: "测试报告生成",
        desc: "可视化报告 + CI/CD 集成 + 回归检测",
        code: `class TestReporter:
    """
    生成可视化测试报告，支持CI/CD集成
    """
    def generate_report(self, all_results: list[TestResults]):
        report = {
            "summary": {
                "total_scenarios": len(all_results),
                "passed": sum(1 for r in all_results if r.passed),
                "failed": sum(1 for r in all_results if not r.passed),
            },
            "dimensions": {
                "latency": self._latency_summary(all_results),
                "accuracy": self._accuracy_summary(all_results),
                "robustness": self._robustness_matrix(all_results),
                "naturalness": self._naturalness_scores(all_results),
            },
            "regression": self._detect_regressions(all_results),
            "noise_matrix": self._noise_snr_vs_accuracy(all_results),
        }
        
        # 输出多种格式
        self._write_html_report(report, "report.html")
        self._write_junit_xml(report, "results.xml")  # CI/CD
        self._write_json(report, "results.json")
        
        # 关键：噪音等级 vs 准确率矩阵
        # SNR(dB) | 意图识别 | 实体提取 | 工具调用
        # 40      | 98%     | 96%     | 97%
        # 25      | 95%     | 91%     | 93%
        # 15      | 88%     | 82%     | 85%
        # 10      | 75%     | 68%     | 70%
        #  5      | 52%     | 41%     | 45%
        
        return report`,
      },
    ],
  },
];

// Architecture overview data
const ARCHITECTURE_FLOW = [
  { from: "YAML Scenario", to: "Orchestrator", label: "解析" },
  { from: "Orchestrator", to: "Audio Sim", label: "生成语音" },
  { from: "Orchestrator", to: "Video Sim", label: "生成画面" },
  { from: "Orchestrator", to: "Noise Engine", label: "混合噪音" },
  { from: "Audio+Noise", to: "Network Sim", label: "网络传输" },
  { from: "Network Sim", to: "System Under Test", label: "推送" },
  { from: "System Under Test", to: "Tool Registry", label: "工具调用" },
  { from: "System Under Test", to: "Evaluator", label: "评估响应" },
];

function CodeBlock({ code }) {
  return (
    <pre
      style={{
        background: "#1a1a2e",
        color: "#e0e0e0",
        padding: "16px",
        borderRadius: "8px",
        fontSize: "11.5px",
        lineHeight: "1.5",
        overflow: "auto",
        maxHeight: "420px",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
        margin: 0,
        whiteSpace: "pre",
        tabSize: 4,
      }}
    >
      {code}
    </pre>
  );
}

function ModuleCard({ module, isOpen, onToggle, accentColor }) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: "10px",
        border: `1px solid ${accentColor}44`,
        overflow: "hidden",
        marginBottom: "10px",
        boxShadow: isOpen ? `0 4px 20px ${accentColor}22` : "0 1px 4px rgba(0,0,0,0.06)",
        transition: "box-shadow 0.3s ease",
      }}
    >
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          padding: "14px 18px",
          background: isOpen ? `${accentColor}11` : "transparent",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "flex-start",
          gap: "12px",
          textAlign: "left",
          transition: "background 0.2s ease",
        }}
      >
        <span
          style={{
            fontSize: "18px",
            lineHeight: "1",
            transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 0.2s ease",
            marginTop: "2px",
            flexShrink: 0,
          }}
        >
          ▸
        </span>
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontWeight: 700,
              fontSize: "14px",
              color: "#1a1a2e",
              fontFamily: "'Space Mono', monospace",
            }}
          >
            {module.name}
          </div>
          <div
            style={{
              fontSize: "12.5px",
              color: "#666",
              marginTop: "3px",
              lineHeight: "1.4",
            }}
          >
            {module.desc}
          </div>
        </div>
      </button>
      {isOpen && (
        <div style={{ padding: "0 14px 14px" }}>
          <CodeBlock code={module.code} />
        </div>
      )}
    </div>
  );
}

function LayerSection({ layer }) {
  const [openModules, setOpenModules] = useState(new Set());

  const toggleModule = (idx) => {
    setOpenModules((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div
      style={{
        marginBottom: "28px",
        borderRadius: "14px",
        background: layer.color,
        border: `2px solid ${layer.borderColor}`,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "20px 24px 14px",
          borderBottom: `1px solid ${layer.borderColor}44`,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: "20px",
            color: layer.textColor,
            fontFamily: "'Space Mono', monospace",
            fontWeight: 700,
          }}
        >
          {layer.name}
        </h2>
        <p
          style={{
            margin: "4px 0 0",
            fontSize: "13px",
            color: layer.textColor,
            opacity: 0.75,
          }}
        >
          {layer.subtitle}
        </p>
      </div>
      <div style={{ padding: "14px 16px" }}>
        {layer.modules.map((mod, idx) => (
          <ModuleCard
            key={idx}
            module={mod}
            isOpen={openModules.has(idx)}
            onToggle={() => toggleModule(idx)}
            accentColor={layer.borderColor}
          />
        ))}
      </div>
    </div>
  );
}

export default function VoiceTestFramework() {
  const [activeView, setActiveView] = useState("architecture");

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#F5F3EE",
        fontFamily: "'Inter', 'Noto Sans SC', sans-serif",
      }}
    >
      <link
        href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap"
        rel="stylesheet"
      />

      {/* Header */}
      <div
        style={{
          background: "#1a1a2e",
          color: "#fff",
          padding: "32px 28px",
          borderBottom: "4px solid #e94560",
        }}
      >
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          <div
            style={{
              fontSize: "11px",
              letterSpacing: "3px",
              textTransform: "uppercase",
              color: "#e94560",
              fontFamily: "'Space Mono', monospace",
              marginBottom: "8px",
            }}
          >
            Testing Framework Design
          </div>
          <h1
            style={{
              margin: 0,
              fontSize: "28px",
              fontWeight: 700,
              fontFamily: "'Space Mono', monospace",
              lineHeight: 1.3,
            }}
          >
            实时语音对话系统
            <br />
            端到端测试框架
          </h1>
          <p
            style={{
              margin: "10px 0 0",
              fontSize: "14px",
              color: "#aaa",
              lineHeight: 1.6,
            }}
          >
            模拟真实用户交互 · 多模态输入 · 噪音与网络 · Tool Use · 自动化评估
          </p>
        </div>
      </div>

      {/* Nav */}
      <div
        style={{
          background: "#fff",
          borderBottom: "1px solid #ddd",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}
      >
        <div
          style={{
            maxWidth: 900,
            margin: "0 auto",
            display: "flex",
            gap: "0",
          }}
        >
          {[
            { id: "architecture", label: "📐 架构总览" },
            { id: "layers", label: "🧱 分层详解" },
            { id: "integration", label: "🔗 集成方式" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveView(tab.id)}
              style={{
                padding: "14px 22px",
                border: "none",
                borderBottom:
                  activeView === tab.id
                    ? "3px solid #e94560"
                    : "3px solid transparent",
                background: "none",
                cursor: "pointer",
                fontSize: "13.5px",
                fontWeight: activeView === tab.id ? 700 : 500,
                color: activeView === tab.id ? "#1a1a2e" : "#888",
                fontFamily: "'Inter', sans-serif",
                transition: "all 0.2s ease",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "28px 20px" }}>
        {activeView === "architecture" && <ArchitectureView />}
        {activeView === "layers" && <LayersView />}
        {activeView === "integration" && <IntegrationView />}
      </div>
    </div>
  );
}

function ArchitectureView() {
  return (
    <div>
      {/* Data flow diagram */}
      <div
        style={{
          background: "#1a1a2e",
          borderRadius: "14px",
          padding: "28px",
          marginBottom: "28px",
          color: "#e0e0e0",
          fontFamily: "'Space Mono', monospace",
          fontSize: "12px",
          lineHeight: "1.8",
          overflow: "auto",
        }}
      >
        <div style={{ color: "#e94560", fontWeight: 700, marginBottom: "16px", fontSize: "14px" }}>
          ▸ 数据流架构
        </div>
        <pre style={{ margin: 0, whiteSpace: "pre", color: "#ccc" }}>
{`┌─────────────────────────────────────────────────────────────────────┐
│                    🎬 Scenario Engine (YAML/DSL)                    │
│         定义: 对话流程 · 时间线 · 环境 · 断言条件                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │ 编排调度
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  🎤 Audio Sim   │ │  📹 Video Sim   │ │  🌍 Environment │
│  ─────────────  │ │  ─────────────  │ │  ─────────────  │
│  TTS/录音       │ │  相机模拟       │ │  噪音引擎       │
│  语音风格       │ │  屏幕共享       │ │  物理事件       │
│  打断/插话      │ │  文档/物体      │ │  网络模拟       │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │ 混合 + 网络传输模拟
                             ▼
              ┌──────────────────────────────┐
              │   🖥️  System Under Test      │
              │   (被测试的语音对话系统)        │
              └──────┬────────────────┬──────┘
                     │                │
              ┌──────▼──────┐  ┌─────▼───────┐
              │ 🔧 Tool Use │  │ 📤 Response  │
              │  Mock Tools │  │  Audio/Text  │
              │  延迟/失败  │  │              │
              └─────────────┘  └──────┬───────┘
                                      │
                             ┌────────▼────────┐
                             │  📊 Evaluator   │
                             │  ─────────────  │
                             │  延迟 · 准确性  │
                             │  自然度 · 鲁棒性│
                             │  LLM-as-Judge  │
                             └────────┬────────┘
                                      │
                             ┌────────▼────────┐
                             │  📋 报告 & CI   │
                             │  HTML · JUnit   │
                             │  回归检测        │
                             └─────────────────┘`}
        </pre>
      </div>

      {/* Key design principles */}
      <div
        style={{
          background: "#fff",
          borderRadius: "14px",
          padding: "24px",
          marginBottom: "20px",
          border: "1px solid #e0ddd5",
        }}
      >
        <h3
          style={{
            margin: "0 0 16px",
            fontFamily: "'Space Mono', monospace",
            fontSize: "16px",
            color: "#1a1a2e",
          }}
        >
          🏗️ 核心设计原则
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
          {[
            {
              title: "声明式场景定义",
              desc: "用 YAML 描述测试场景而非写代码，降低编写门槛。支持时间线、条件分支、循环。",
              icon: "📝",
            },
            {
              title: "分层解耦架构",
              desc: "音频、视频、噪音、网络、工具各层独立，可自由组合。替换任一层不影响其他层。",
              icon: "🧱",
            },
            {
              title: "真实性优先",
              desc: "不是简单注入文本，而是生成真实音频流、模拟真实网络抖动、引入真实环境噪音。",
              icon: "🎯",
            },
            {
              title: "多维度评估",
              desc: "延迟、准确性、自然度、鲁棒性独立评分。使用 LLM-as-Judge 评估对话自然度。",
              icon: "📊",
            },
            {
              title: "CI/CD 友好",
              desc: "输出 JUnit XML 格式，支持回归检测。可在每次提交后自动运行关键场景。",
              icon: "🔄",
            },
            {
              title: "渐进式复杂度",
              desc: "从简单的「安静环境单轮对话」逐步增加噪音、打断、网络波动、多模态输入。",
              icon: "📈",
            },
          ].map((p, i) => (
            <div
              key={i}
              style={{
                padding: "14px",
                background: "#f9f7f2",
                borderRadius: "10px",
                border: "1px solid #e8e4db",
              }}
            >
              <div style={{ fontSize: "20px", marginBottom: "6px" }}>{p.icon}</div>
              <div
                style={{
                  fontWeight: 700,
                  fontSize: "13px",
                  color: "#1a1a2e",
                  marginBottom: "4px",
                }}
              >
                {p.title}
              </div>
              <div style={{ fontSize: "12px", color: "#666", lineHeight: 1.5 }}>
                {p.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* SUT interface */}
      <div
        style={{
          background: "#fff",
          borderRadius: "14px",
          padding: "24px",
          border: "1px solid #e0ddd5",
        }}
      >
        <h3
          style={{
            margin: "0 0 14px",
            fontFamily: "'Space Mono', monospace",
            fontSize: "16px",
            color: "#1a1a2e",
          }}
        >
          🔌 被测系统接口 (SUT Interface)
        </h3>
        <p style={{ fontSize: "13px", color: "#666", margin: "0 0 14px", lineHeight: 1.6 }}>
          框架通过统一接口与被测系统对接，支持任意语音对话系统：
        </p>
        <CodeBlock
          code={`class VoiceSystemInterface(Protocol):
    """被测系统必须实现此接口"""
    
    async def push_audio(self, chunk: AudioChunk) -> None:
        """推送音频数据（模拟麦克风输入）"""
        ...
    
    async def push_video(self, frame: VideoFrame) -> None:
        """推送视频帧（模拟相机/屏幕输入）"""
        ...
    
    async def get_response_stream(self) -> AsyncIterator[ResponseEvent]:
        """获取系统响应流（音频/文本/工具调用）"""
        ...
    
    async def register_tool_handler(self, name: str, handler) -> None:
        """注册工具调用处理器"""
        ...
    
    @property
    def state(self) -> SystemState:
        """当前系统状态（说话中/等待/处理中）"""
        ...

# 适配器示例 - 对接 OpenAI Realtime API
class OpenAIRealtimeAdapter(VoiceSystemInterface):
    def __init__(self, api_key: str, model: str):
        self.ws = WebSocketClient(
            "wss://api.openai.com/v1/realtime",
            headers={"Authorization": f"Bearer {api_key}"}
        )
    async def push_audio(self, chunk: AudioChunk):
        await self.ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(chunk.data).decode()
        }))`}
        />
      </div>
    </div>
  );
}

function LayersView() {
  return (
    <div>
      {LAYERS.map((layer) => (
        <LayerSection key={layer.id} layer={layer} />
      ))}
    </div>
  );
}

function IntegrationView() {
  return (
    <div>
      <div
        style={{
          background: "#fff",
          borderRadius: "14px",
          padding: "24px",
          marginBottom: "20px",
          border: "1px solid #e0ddd5",
        }}
      >
        <h3 style={{ margin: "0 0 14px", fontFamily: "'Space Mono', monospace", fontSize: "16px" }}>
          🚀 快速开始：编写你的第一个测试
        </h3>
        <CodeBlock
          code={`# test_hotel_booking.py
import pytest
from voice_test_framework import (
    ScenarioOrchestrator, 
    AudioStreamSimulator,
    NoiseEngine, 
    MockToolRegistry,
    EvaluationFramework,
)

@pytest.fixture
def framework():
    """初始化测试框架"""
    orch = ScenarioOrchestrator()
    
    # 注册各模拟层
    orch.register_layer("audio", AudioStreamSimulator(
        tts_provider="azure",  # 或 "google", "elevenlabs"
        sample_rate=16000,
    ))
    orch.register_layer("environment", NoiseEngine(
        profile="office", snr_db=25
    ))
    orch.register_layer("video", VideoStreamSimulator(fps=15))
    orch.register_layer("tools", MockToolRegistry())
    orch.register_layer("eval", EvaluationFramework())
    
    return orch

@pytest.fixture
def sut():
    """被测系统"""
    return OpenAIRealtimeAdapter(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-realtime-preview"
    )

# ═══════════════════════════════════════════════════
#  测试用例
# ═══════════════════════════════════════════════════

class TestHotelBooking:
    """酒店预订场景测试套件"""
    
    async def test_basic_booking_flow(self, framework, sut):
        """基本预订流程 - 安静环境"""
        results = await framework.run(
            scenario="scenarios/hotel_booking_basic.yaml",
            system=sut,
        )
        assert results.all_passed()
        assert results.latency.p50_first_byte < 500  # ms
    
    async def test_booking_with_cafe_noise(self, framework, sut):
        """咖啡馆噪音下的预订"""
        results = await framework.run(
            scenario="scenarios/hotel_booking_noisy.yaml",
            system=sut,
        )
        assert results.tool_calls.assert_called("check_availability")
        assert results.accuracy.intent_recognition > 0.85
    
    async def test_user_interrupts_during_options(self, framework, sut):
        """用户在系统列举选项时打断"""
        results = await framework.run(
            scenario="scenarios/hotel_booking_interrupt.yaml",
            system=sut,
        )
        # 系统应该停止列举，直接响应打断内容
        assert results.barge_in.was_handled
        assert results.barge_in.response_latency < 300  # ms
    
    async def test_tool_failure_recovery(self, framework, sut):
        """预订接口失败后的恢复"""
        framework.layers["tools"].register(
            "create_booking",
            handler=lambda _: raise_(ServiceError("timeout")),
            failure_rate=1.0,  # 100% 失败
        )
        results = await framework.run(
            scenario="scenarios/hotel_booking_basic.yaml",
            system=sut,
        )
        # 系统应该告知用户失败并提供替代方案
        assert "sorry" in results.last_response.text.lower() or \\
               "抱歉" in results.last_response.text
    
    @pytest.mark.parametrize("snr_db", [40, 25, 15, 10, 5])
    async def test_noise_robustness_matrix(self, framework, sut, snr_db):
        """不同噪音等级下的鲁棒性矩阵"""
        framework.layers["environment"].set_snr(snr_db)
        results = await framework.run(
            scenario="scenarios/hotel_booking_basic.yaml",
            system=sut,
        )
        # 记录不同 SNR 下的准确率，生成鲁棒性矩阵
        results.tag(f"snr_{snr_db}")
        
    async def test_multimodal_screen_share(self, framework, sut):
        """用户共享屏幕询问内容"""
        results = await framework.run(
            scenario="scenarios/screen_share_help.yaml",
            system=sut,
        )
        # 系统应该能理解屏幕内容并结合语音回答
        assert results.accuracy.visual_grounding > 0.8`}
        />
      </div>

      <div
        style={{
          background: "#fff",
          borderRadius: "14px",
          padding: "24px",
          marginBottom: "20px",
          border: "1px solid #e0ddd5",
        }}
      >
        <h3 style={{ margin: "0 0 14px", fontFamily: "'Space Mono', monospace", fontSize: "16px" }}>
          📦 推荐项目结构
        </h3>
        <CodeBlock
          code={`voice-test-framework/
├── pyproject.toml
├── src/
│   └── voice_test_framework/
│       ├── __init__.py
│       ├── core/
│       │   ├── orchestrator.py      # 场景编排器
│       │   ├── clock.py             # 模拟时钟
│       │   ├── interfaces.py        # Protocol 定义
│       │   └── results.py           # 测试结果数据结构
│       ├── simulation/
│       │   ├── audio.py             # 音频流模拟 ← 你已有的部分
│       │   ├── video.py             # 视频/屏幕模拟
│       │   ├── barge_in.py          # 打断模拟
│       │   ├── noise.py             # 噪音引擎
│       │   ├── network.py           # 网络状况模拟
│       │   └── physical_world.py    # 物理世界模拟
│       ├── tools/
│       │   ├── registry.py          # Mock Tool 注册
│       │   ├── asserter.py          # 工具调用断言
│       │   └── builtin_mocks.py     # 常用工具 mock
│       ├── evaluation/
│       │   ├── framework.py         # 评估框架
│       │   ├── latency.py           # 延迟评分
│       │   ├── accuracy.py          # 准确性评分
│       │   ├── naturalness.py       # 自然度 (LLM-as-Judge)
│       │   └── robustness.py        # 鲁棒性评分
│       ├── adapters/
│       │   ├── openai_realtime.py   # OpenAI Realtime API
│       │   ├── google_duplex.py     # Google 适配器
│       │   └── custom_websocket.py  # 通用 WebSocket 适配
│       └── reporting/
│           ├── html_report.py       # HTML 可视化报告
│           ├── junit.py             # JUnit XML (CI/CD)
│           └── regression.py        # 回归检测
├── scenarios/                        # YAML 测试场景
│   ├── hotel_booking_basic.yaml
│   ├── hotel_booking_noisy.yaml
│   ├── hotel_booking_interrupt.yaml
│   ├── screen_share_help.yaml
│   └── stress_test_100_turns.yaml
├── assets/                           # 音频/视频素材
│   ├── noise/
│   │   ├── cafe_ambient.wav
│   │   ├── office_ambient.wav
│   │   └── phone_ring.wav
│   ├── voices/                       # 预录音频
│   └── images/                       # 测试图片
└── tests/
    ├── test_hotel_booking.py
    ├── test_noise_robustness.py
    └── test_barge_in.py`}
        />
      </div>

      <div
        style={{
          background: "#fff",
          borderRadius: "14px",
          padding: "24px",
          border: "1px solid #e0ddd5",
        }}
      >
        <h3 style={{ margin: "0 0 14px", fontFamily: "'Space Mono', monospace", fontSize: "16px" }}>
          🗺️ 实施路线图
        </h3>
        <div style={{ fontSize: "13.5px", lineHeight: 1.8, color: "#333" }}>
          {[
            {
              phase: "Phase 1 — 基础骨架 (1-2周)",
              items: [
                "核心 Orchestrator + SimulatedClock",
                "YAML 场景解析器",
                "集成你现有的 Audio Stream 模拟器",
                "基础断言框架",
                "一个 SUT 适配器 (如 OpenAI Realtime)",
              ],
              color: "#82B366",
            },
            {
              phase: "Phase 2 — 环境模拟 (2-3周)",
              items: [
                "噪音引擎 (环境底噪 + 瞬态事件)",
                "网络状况模拟",
                "Barge-in / 打断模拟",
                "Mock Tool Registry",
              ],
              color: "#6C8EBF",
            },
            {
              phase: "Phase 3 — 多模态 + 评估 (2-3周)",
              items: [
                "视频/屏幕输入模拟",
                "物理世界事件模拟",
                "LLM-as-Judge 自然度评估",
                "鲁棒性矩阵生成",
                "HTML 报告 + CI/CD 集成",
              ],
              color: "#D6B656",
            },
            {
              phase: "Phase 4 — 规模化 (持续)",
              items: [
                "场景库积累 (50+ 场景)",
                "参数化测试 + 模糊测试",
                "分布式执行",
                "回归检测 + 性能趋势追踪",
              ],
              color: "#B85450",
            },
          ].map((p, i) => (
            <div
              key={i}
              style={{
                marginBottom: "18px",
                paddingLeft: "18px",
                borderLeft: `4px solid ${p.color}`,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "14px", color: "#1a1a2e", marginBottom: "6px" }}>
                {p.phase}
              </div>
              <div style={{ color: "#555", fontSize: "13px" }}>
                {p.items.map((item, j) => (
                  <div key={j} style={{ marginBottom: "2px" }}>
                    → {item}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
