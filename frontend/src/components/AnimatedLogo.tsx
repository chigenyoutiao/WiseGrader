import logoImg from '../assets/logo.png'; // 确保这是你抠好的透明 PNG

interface AnimatedLogoProps {
  className?: string;
  size?: number;
}

export default function AnimatedLogo({ className = "", size = 40 }: AnimatedLogoProps) {
  // 定义背景颜色变量
  const bgColor = 'rgb(1, 32, 60)';

  return (
    <div 
      className={`relative flex items-center justify-center ${className}`} 
      style={{ width: size, height: size }}
    >
      {/* 1. SVG 圆角六边形底座 (纯深色背景) */}
      <svg 
        viewBox="0 0 100 100" 
        // 给底座加一点点深色投影，增加立体感
        className="absolute inset-0 w-full h-full drop-shadow-md"
      >
        {/* 🟢 改动1：移除了 <defs> 渐变定义，因为不再需要了 */}
        
        <polygon
          points="50 5, 93.3 30, 93.3 70, 50 95, 6.7 70, 6.7 30"
          // 🟢 改动2：填充和描边都使用指定的 RGB 纯色
          fill={bgColor}
          stroke={bgColor}
          strokeWidth="12"       
          strokeLinejoin="round" 
        />
      </svg>

      {/* 2. 你的对号图片 (前景层 + 光晕特效) */}
      <img 
        src={logoImg} 
        alt="WiseGrader Logo"
        // 稍微调整大小比例，让构图更舒服
        className="relative z-10 w-[75%] h-[75%] object-contain"
        style={{
          // 🟢 改动3：添加多层光晕效果
          // drop-shadow 能贴合图片非透明区域的边缘产生阴影/光晕。
          // 这里叠加了两层：一层紧贴的亮光(青白色)，一层扩散的柔光(青蓝色)，营造强烈的发光感。
          filter: `
            drop-shadow(0 0 4px rgba(200, 240, 255, 0.8)) 
            drop-shadow(0 0 12px rgba(0, 190, 255, 0.6))
          `
        }}
      />
    </div>
  );
}