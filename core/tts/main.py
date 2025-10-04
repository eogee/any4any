from indextts.infer import IndexTTS

# 初始化
tts = IndexTTS(
    cfg_path="/mnt/c/models/IndexTTS-1.5/config.yaml",
    model_dir="/mnt/c/models/IndexTTS-1.5",
    is_fp16=True,  # 推荐使用FP16加速
    use_cuda_kernel=True  # 启用CUDA内核以获得更好的性能
)

# 批量推理(长文本优化)
output = tts.infer_fast(
    audio_prompt="/mnt/c/ProgramMine/any4any/core/tts/prompt.wav",
    text="""01、《撒谎》母亲打来电话，说父亲上山放羊，不小心摔断了一条胳膊。一个小时后，我匆匆赶到医院，见到了手术后还处于麻醉状态的父亲。""",
    output_path="/mnt/c/ProgramMine/any4any/core/tts/output/audio.wav",
    max_text_tokens_per_sentence=100,  # 每句最大token数
    sentences_bucket_max_size=4,      # 批量大小
    do_sample=True,                  # 采样参数
    top_p=0.8,
    temperature=1.0
)