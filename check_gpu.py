import sys
try:
    import torch
    print(f'PyTorch Version: {torch.__version__}')
    print(f'PyTorch CUDA Available: {torch.cuda.is_available()}')
except Exception as e:
    print(f'PyTorch Error: {e}')

try:
    import onnxruntime as ort
    print(f'ONNX Runtime Version: {ort.__version__}')
    print(f'ONNX Providers: {ort.get_available_providers()}')
except Exception as e:
    print(f'ONNX Error: {e}')
