import { useEffect, useRef } from 'react';

export default function MouseFollower() {  const glowRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const particleTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      // 更新光晕位置
      if (glowRef.current) {
        glowRef.current.style.left = `${e.clientX}px`;
        glowRef.current.style.top = `${e.clientY}px`;
      }

      // 创建粒子效果 - 增加生成频率和数量
      if (containerRef.current && Math.random() > 0.3) {
        // 每次生成 2-3 个粒子
        const particleCount = 2 + Math.floor(Math.random() * 2);
        for (let i = 0; i < particleCount; i++) {
          const particle = document.createElement('div');
          particle.className = 'mouse-particle';
          const angle = Math.random() * Math.PI * 2;
          const distance = 30 + Math.random() * 50;
          const tx = Math.cos(angle) * distance;
          const ty = Math.sin(angle) * distance;
          
          particle.style.setProperty('--tx', `${tx}px`);
          particle.style.setProperty('--ty', `${ty}px`);
          particle.style.left = `${e.clientX}px`;
          particle.style.top = `${e.clientY}px`;
          
          containerRef.current.appendChild(particle);
          
          // 清理粒子
          setTimeout(() => {
            particle.remove();
          }, 1200);
        }
      }

      // 创建波纹效果（更频繁）
      if (Math.random() > 0.85) {
        const ripple = document.createElement('div');
        ripple.className = 'ripple-circle';
        ripple.style.left = `${e.clientX}px`;
        ripple.style.top = `${e.clientY}px`;
        document.body.appendChild(ripple);
        
        setTimeout(() => {
          ripple.remove();
        }, 3000);
      }
    };

    const handleMouseLeave = () => {
      // 鼠标离开时隐藏光晕
      if (glowRef.current) {
        glowRef.current.style.opacity = '0';
      }
    };

    const handleMouseEnter = () => {
      // 鼠标进入时显示光晕
      if (glowRef.current) {
        glowRef.current.style.opacity = '1';
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);
    document.addEventListener('mouseenter', handleMouseEnter);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      document.removeEventListener('mouseenter', handleMouseEnter);
      if (particleTimeoutRef.current) {
        clearTimeout(particleTimeoutRef.current);
      }
    };
  }, []);

  return (
    <>
      <div ref={glowRef} className="mouse-glow" style={{ opacity: 0 }} />
      <div ref={containerRef} className="mouse-follower" />
    </>
  );
}

