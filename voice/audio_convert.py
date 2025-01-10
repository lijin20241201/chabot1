import shutil
import wave
from common.log import logger
try:
    import pysilk
except ImportError:
    logger.debug("import pysilk failed, wechaty voice message will not be supported.")

from pydub import AudioSegment
sil_supports = [8000, 12000, 16000, 24000, 32000, 44100, 48000]  # slk转wav时，支持的采样率
# 找到最接近的支持的采样率
def find_closest_sil_supports(sample_rate):
    if sample_rate in sil_supports: # 如果传入的采样率在支持的列表内,直接返回
        return sample_rate
    closest = 0
    mindiff = 9999999 # 最小差别
    for rate in sil_supports: # 遍历支持的采样率
        diff = abs(rate - sample_rate) # 获取差别
        if diff < mindiff:  # 如果差别比mindiff小
            closest = rate # 更新最接近传入的受支持的采样率
            mindiff = diff # 更新mindiff
    return closest
# 这段代码的功能是从 WAV 文件中提取 PCM（脉冲编码调制）数据。
def get_pcm_from_wav(wav_path):
    # 这一行使用 Python 标准库中的 wave 模块的 open 函数打开指定的 WAV 文件。"
    wav = wave.open(wav_path, "rb")
   #  wav.getnframes()：获取 WAV 文件中的总帧数。每个音频帧包含一个或多个样本（取决于采样格式和通道数）。
    # wav.readframes(n)：读取文件中的 n 帧数据，并返回包含 PCM 数据的字节串。n 就是 wav.getnframes() 返回的帧数。
    # 例如，如果一个 WAV 文件的采样率是 44.1kHz，单声道（1 通道），并且录音时长为 1 秒，那么总帧数 getnframes() 会返
    # 回 44,100（即 44.1kHz × 1 秒）。
    # 如果你调用 wav.readframes(wav.getnframes())，那么会读取整个 WAV 文件的所有帧。
    return wav.readframes(wav.getnframes())
# 用于将任意格式的音频文件转换成 MP3 格式，支持的输入格式有 MP3、.sil、.silk、.slk 以及其他音频格式。
# any_path: 输入的音频文件路径，可以是任意格式的音频文件（如 .mp3、.flac、.wav 等）。
# mp3_path: 输出的目标 MP3 文件路径。
def any_to_mp3(any_path, mp3_path):
    # 如果输入文件已经是 .mp3 格式，直接通过 shutil.copy2 将文件拷贝到目标路径 mp3_path，不做任何转换。
    if any_path.endswith(".mp3"):
        shutil.copy2(any_path, mp3_path)
        return
    # 如果输入文件是 .sil、.silk 或 .slk 格式，则调用 sil_to_wav 函数进行转换。
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        # sil_to_wav(any_path, any_path) 的作用应该是将 .sil 或 .silk 格式转换成 WAV 格式，这里直接修改了 any_path 
        # 为输出的 WAV 文件路径。这样做是为了确保后续代码处理的是已经转码后的文件。
        sil_to_wav(any_path, any_path)
    # pydub 通过文件内容（如 WAV 格式的头信息）来识别文件类型，而不是完全依赖文件扩展名。因此，即使文件名是 any.sil，如果它的内容是 WAV 格式，
    audio = AudioSegment.from_file(any_path)
    audio.export(mp3_path, format="mp3")

# 用于将任意格式的音频文件转换成 WAV 格式，支持的输入格式有 WAV、.sil、.silk、.slk 和其他音频格式（如 MP3、FLAC 等）。
def any_to_wav(any_path, wav_path):
    # 如果输入文件已经是 .wav 格式，直接通过 shutil.copy2 将文件拷贝到目标路径 wav_path，不做任何转换。
    if any_path.endswith(".wav"):
        shutil.copy2(any_path, wav_path)
        return
    # 如果输入文件是 .sil、.silk 或 .slk 格式，则调用 sil_to_wav 函数进行转换。
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        return sil_to_wav(any_path, wav_path)
    # 如果文件不是 WAV 格式，也不是 .sil、.silk、.slk 格式，那么就使用 AudioSegment 来处理其他格式的音频文件。A
    # udioSegment.from_file 会根据文件类型自动加载适当的解码器来读取文件。
    audio = AudioSegment.from_file(any_path)
   # 将音频文件的采样率设置为 8000 Hz。这里是为了符合某些语音识别系统（如百度语音转写）的要求。语音识别系统一
    # 般需要使用较低的采样率
    audio.set_frame_rate(8000)    # 百度语音转写支持8000采样率, pcm_s16le, 单通道语音识别
    # 将音频设置为单声道（mono）。语音识别系统通常也只需要单声道音频，因为这样能够减少计算量并提高识别效果。
    audio.set_channels(1)
    # 最后，将处理过的音频导出为 WAV 格式，使用 pcm_s16le 编解码器。pcm_s16le 是一种常见的音频编码格式，表示每个采样点使用 
    # 16 位有符号小端格式存储数据，通常用于语音识别和其他低延迟音频应用。
    audio.export(wav_path, format="wav", codec='pcm_s16le')

# 将任意格式的音频文件转换为 SIL 格式。SIL（Silk）是一种音频编码格式，通常用于语音压缩，尤其是在 Skype 等 VoIP 应用中。
def any_to_sil(any_path, sil_path):
    # 这段代码首先检查输入文件是否已经是 SIL 格式。如果输入文件的扩展名是 .sil、.silk 或 .slk，说明它已经是 SIL 格式。
    # 如果是 SIL 格式，则直接将源文件通过 shutil.copy2 拷贝到目标路径 sil_path，并返回 10000（假设这是音频的时长，单位是毫秒）。
    # shutil.copy2 会复制文件并保留文件的元数据
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        shutil.copy2(any_path, sil_path)
        return 10000
    # 这行代码使用 pydub 的 AudioSegment.from_file 方法加载输入的音频文件。from_file 会自动根据文件类型解码音频数据。
    audio = AudioSegment.from_file(any_path)
    # 调用 find_closest_sil_supports(audio.frame_rate) 来查找与输入音频的采样率最接近的 SIL 编码支持的采样率。S
    # IL 编解码器通常支持一组固定的采样率，因此需要将输入音频的采样率转换为支持的采样率。
    rate = find_closest_sil_supports(audio.frame_rate)
    # audio.set_sample_width(2)：这行代码将音频的样本宽度（sample_width）设置为 2 字节，即 16 位深度。SIL 编码通常要求
    # 音频是 16 位的 PCM 格式。
    # audio.set_frame_rate(rate)：这行代码将音频的采样率设置为前面找到的 rate，即转换为 SIL 支持的采样率。
    pcm_s16 = audio.set_sample_width(2)
    pcm_s16 = pcm_s16.set_frame_rate(rate)
    # 提取 PCM 数据并进行 SIL 编码,pcm_s16.raw_data 提取的是经过处理后的 PCM 音频数据（即 16 位深度、指定采样率的原始音频数据）
    # 。这个数据是音频的 原始字节数据，不包含任何音频格式头部信息。
    wav_data = pcm_s16.raw_data
    # ysilk.encode(wav_data, data_rate=rate, sample_rate=rate) 使用 pysilk 库的 encode 方法将原始的 PCM 数据编码为 
    # SIL 格式。encode 方法会根据指定的 data_rate 和 sample_rate 将 PCM 数据转换为 SIL 格式的压缩数据。
    silk_data = pysilk.encode(wav_data, data_rate=rate, sample_rate=rate)
    # 这段代码将生成的 SIL 数据写入到目标文件路径 sil_path 中。"wb" 模式表示以二进制方式打开文件并写入数据。
    with open(sil_path, "wb") as f:
        f.write(silk_data)
    # audio.duration_seconds * 1000 将时长转换为毫秒，并作为函数的返回值。这个返回值通常用于表示音频文件的时长，可能用
    # 于音频播放时长等场景。
    return audio.duration_seconds * 1000

# 将任意格式的音频文件转换为 AMR 格式。AMR（Adaptive Multi-Rate）是一种音频压缩格式，通常用于语音通信
# any_path：输入的音频文件路径，可以是任何格式的音频文件。
# amr_path：输出的 AMR 文件路径，即转换后的文件路径。
def any_to_amr(any_path, amr_path):
    # 这段代码检查输入文件是否已经是 AMR 格式。如果输入文件路径以 .amr 结尾，表示它已经是 AMR 格式，直接通过 
    # shutil.copy2 将源文件拷贝到目标路径 amr_path。
    if any_path.endswith(".amr"):
        shutil.copy2(any_path, amr_path)
        return
    # 这段代码处理了不支持的输入格式，具体来说，如果文件的扩展名是 .sil、.silk 或 .slk（常见于 SILK 格式的文件），则会抛出
    # 一个 NotImplementedError 异常，表示该格式不支持转换为 AMR 格式。
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        raise NotImplementedError("Not support file type: {}".format(any_path))
    # 这两行使用了 pydub 库的 AudioSegment.from_file 方法来加载音频文件。from_file 方法能够自动识别并加载多种常见的音频格式，如 MP3、WAV 等。
    audio = AudioSegment.from_file(any_path)
    # 然后，使用 set_frame_rate(8000) 方法将音频的采样率设置为 8000 Hz，因为 AMR 格式仅支持 8000 Hz 采样率。
    # 这个步骤确保音频符合 AMR 格式的要求。
    audio = audio.set_frame_rate(8000)  
    # 通过 audio.export 方法将音频数据导出为 AMR 格式，并保存到 amr_path 指定的文件路径中。format="amr" 表示输出格式是 AMR。
    audio.export(amr_path, format="amr")
    # 返回音频的时长：将秒转换为毫秒，乘以 1000 后返回音频的时长（单位：毫秒）。这个值表示音频文件的持续时间，
    # 通常可以用来显示音频的播放时长。
    return audio.duration_seconds * 1000

# 将 SILK 格式的音频文件转换成 WAV 格式的音频文件。SILK 是一种由 Skype 开发的音频编解码格式，通常用于 VoIP 通话和语音通信
# rate：音频的采样率，默认值为 24000 Hz。采样率决定了每秒钟采集多少个样本，通常用于音频质量的设定。
def sil_to_wav(silk_path, wav_path, rate: int = 24000):
    # pysilk.decode_file(silk_path, to_wav=True, sample_rate=rate) 会将 SILK 格式的音频数据解码，并按照 WAV 
    # 文件格式组织数据。它不仅包含 PCM 音频数据，还包含 WAV 文件头、格式信息等。
    #  wav_data 是这种完整的 WAV 格式音频数据，它已经包含了标准的 WAV 文件结构，可以直接被写入一个 .wav 文件。
    wav_data = pysilk.decode_file(silk_path, to_wav=True, sample_rate=rate)
    # wav_path：目标 WAV 文件的路径。
    # "wb"：以二进制写模式打开文件，确保数据按照二进制格式写入。
    # f.write(wav_data)：将 wav数据写入到 WAV 文件中
    with open(wav_path, "wb") as f:
        f.write(wav_data)

# 将音频文件按照指定的最大分段长度（以毫秒为单位）进行分割。如果音频文件的长度小于或等于最大分段长度，则直接返回
# 原文件路径；否则，将音频文件分割成多个小片段并返回每个片段的文件路径。
# file_path：音频文件的路径。max_segment_length_ms：指定的最大分段长度，单位为毫秒。
def split_audio(file_path, max_segment_length_ms=60000):
    # 加载音频文件（file_path 是音频文件的路径）。AudioSegment 对象表示音频数据。
    audio = AudioSegment.from_file(file_path)
    audio_length_ms = len(audio) # len(audio) 返回音频的时长，单位是毫秒
    # 这段代码判断音频文件的总时长是否小于或等于指定的最大分段时长 max_segment_length_ms。如果是，则无需分割，直接返回
    # 音频文件的总时长 audio_length_ms,包含原始音频文件路径的列表 [file_path]。
    if audio_length_ms <= max_segment_length_ms:
        return audio_length_ms, [file_path]
    segments = [] # segments = []：初始化一个空列表，用于保存分割后的音频片段。
    # 使用 range() 函数从 0 到 audio_length_ms，步长为 max_segment_length_ms，遍历每个分段的起始位置 start_ms。
    # 这意味着音频将被从 0 毫秒开始，每隔 max_segment_length_ms 毫秒分割一次。
    for start_ms in range(0, audio_length_ms, max_segment_length_ms):
        # 计算分段的结束时间 end_ms，确保它不会超过音频的总时长。
        end_ms = min(audio_length_ms, start_ms + max_segment_length_ms)
        # 从音频中截取从 start_ms 到 end_ms 的部分，生成一个新的音频片段 segment。
        segment = audio[start_ms:end_ms]
        # segments.append(segment)：将分割后的音频片段 segment 添加到 segments 列表中。
        segments.append(segment)
    # 保存分割后的音频文件
    # 获取文件路径的前缀部分（不包含文件扩展名），file_path.rindex(".") 用来找到最后一个点的位置。
    file_prefix = file_path[: file_path.rindex(".")]
    # 提取音频文件的扩展名（例如 mp3、wav 等）。
    format = file_path[file_path.rindex(".") + 1 :]
    files = [] # 初始化一个空列表，用来保存分割后生成的文件路径。
    # 遍历所有分割后的音频片段 segments，并为每个片段生成新的文件路径：
    for i, segment in enumerate(segments):
        # 生成新的文件路径，文件名由原文件名的前缀部分和序号（i+1）组成，扩展名为 format。
        path = f"{file_prefix}_{i+1}" + f".{format}"
        # 将音频片段 segment 导出到指定路径 path，并保留原文件的格式（如 mp3 或 wav）。
        segment.export(path, format=format)
        # 将新生成的文件路径添加到 files 列表中。
        files.append(path)
    # 函数最后返回两个值,audio_length_ms：原始音频的时长（毫秒）。files：包含所有分割后音频文件路径的列表。
    return audio_length_ms, files