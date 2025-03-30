import os
import argparse
import struct
import logging
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 默认路径配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_PATH = SCRIPT_DIR
DEFAULT_OUTPUT_PATH = os.path.join(SCRIPT_DIR, 'output')

def convert_image(input_path, output_path, gray_level, brightness=0):
    try:
        img = Image.open(input_path).convert('RGB')
        orig_width, orig_height = img.size
        
        # 尺寸缩放逻辑保持不变
        max_width, max_height = 296, 128
        ratio = min(max_width/orig_width, max_height/orig_height)
        if ratio < 1:
            new_size = (int(orig_width*ratio), int(orig_height*ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logging.info(f"Resized {input_path} from {orig_width}x{orig_height} to {new_size}")
        else:
            new_size = (orig_width, orig_height)
        new_width, new_height = new_size

        # 灰度处理逻辑保持不变
        gray_img = img.convert('L')
        if brightness != 0:
            factor = 1 + brightness/100
            gray_img = gray_img.point(lambda x: min(255, max(0, int(x * factor))))
            logging.debug(f"Applied brightness factor: {factor:.2f}")

        divisor = 256 // gray_level
        quantized = gray_img.point(lambda x: (gray_level - 1) - (x // divisor))

        bit_params = {
            2: (1, 8), 4: (2, 4), 16: (4, 2)
        }
        bits, alignment = bit_params[gray_level]
        padded_width = ((new_width + alignment -1) // alignment) * alignment

        data = bytearray()
        for y in range(new_height):
            row = [quantized.getpixel((x, y)) for x in range(new_width)]
            row += [0] * (padded_width - new_width)

            byte_row = bytearray()
            if gray_level == 2:
                for i in range(0, padded_width, 8):
                    byte = 0
                    for j in range(8):
                        byte |= (row[i+j] & 0x01) << (7 - j)
                    byte_row.append(byte)
            elif gray_level == 4:
                for i in range(0, padded_width, 4):
                    byte = 0
                    for j in range(4):
                        byte |= (row[i+j] & 0x03) << (6 - j*2)
                    byte_row.append(byte)
            elif gray_level == 16:
                for i in range(0, padded_width, 2):
                    byte = ((row[i] & 0x0F) << 4) | (row[i+1] & 0x0F)
                    byte_row.append(byte)
            data += byte_row

        header = struct.pack('<BBHH', 0, bits, new_width, new_height)
        with open(output_path, 'wb') as f:
            f.write(header)
            f.write(data)
        logging.info(f"Success: {input_path} -> {output_path}")

    except Exception as e:
        logging.error(f"Failed to process {input_path}: {str(e)}")

def process_path(input_path, output_root, gray_level, brightness):
    # 增强路径处理逻辑
    original_input = input_path
    
    # 检查是否为绝对路径
    if not os.path.isabs(input_path):
        # 尝试拼接默认输入路径
        possible_path = os.path.join(DEFAULT_INPUT_PATH, input_path)
        if os.path.exists(possible_path):
            input_path = possible_path
            logging.info(f"Resolved path: {original_input} -> {input_path}")
        else:
            # 尝试直接查找原始路径
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"路径不存在: {input_path}")

    # 文件/目录处理逻辑保持不变
    if os.path.isfile(input_path):
        if input_path.lower().endswith(('.jpg', '.jpeg', '.bmp', '.png')):
            filename = os.path.splitext(os.path.basename(input_path))[0] + '.lbm'
            output_path = os.path.join(output_root, filename)
            convert_image(input_path, output_path, gray_level, brightness)
    else:
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.bmp', '.png')):
                    input_file = os.path.join(root, file)
                    rel_path = os.path.relpath(input_file, input_path)
                    output_subdir = os.path.join(output_root, os.path.dirname(rel_path))
                    os.makedirs(output_subdir, exist_ok=True)
                    output_name = os.path.splitext(file)[0] + '.lbm'
                    output_path = os.path.join(output_subdir, output_name)
                    convert_image(input_file, output_path, gray_level, brightness)

def main():
    parser = argparse.ArgumentParser(description='LBM图像转换器 v2.3')
    parser.add_argument('-i', '--input', 
                       help=f'输入文件/目录（默认：{DEFAULT_INPUT_PATH}）')
    parser.add_argument('-o', '--output', 
                       help=f'输出目录（默认：{DEFAULT_OUTPUT_PATH}）')
    parser.add_argument('-g', '--gray', type=int, choices=[2,4,16], required=True,
                       help='灰度阶数 (2/4/16)')
    parser.add_argument('-b', '--brightness', type=int, default=0,
                       help='亮度调节百分比(-100~100)，默认0')
    
    args = parser.parse_args()

    # 创建默认目录（带异常处理）
    try:
        os.makedirs(DEFAULT_INPUT_PATH, exist_ok=True)
        os.makedirs(DEFAULT_OUTPUT_PATH, exist_ok=True)
    except PermissionError:
        logging.error("无法创建默认目录，请运行：termux-setup-storage")
        return

    # 处理输入路径（增强版）
    final_input = args.input or DEFAULT_INPUT_PATH
    
    # 路径解析优先级：
    # 1. 绝对路径直接使用
    # 2. 相对路径优先在默认输入目录查找
    # 3. 最后尝试原始路径
    if not os.path.exists(final_input):
        if os.path.isabs(final_input):
            raise FileNotFoundError(f"绝对路径不存在: {final_input}")
            
        # 尝试在默认输入目录查找
        possible_path = os.path.join(DEFAULT_INPUT_PATH, final_input)
        if os.path.exists(possible_path):
            final_input = possible_path
        else:
            # 最后尝试原始路径
            if not os.path.exists(final_input):
                raise FileNotFoundError(f"路径不存在: {final_input}")

    # 处理输出路径
    final_output = args.output or DEFAULT_OUTPUT_PATH
    if not os.path.isabs(final_output):
        final_output = os.path.join(DEFAULT_OUTPUT_PATH, final_output)
    
    # 执行转换
    try:
        process_path(final_input, final_output, args.gray, args.brightness)
    except Exception as e:
        logging.error(f"转换失败: {str(e)}")
        if "Permission denied" in str(e):
            logging.info("请确保已授予存储权限，在Termux中运行：termux-setup-storage")

if __name__ == '__main__':
    main()