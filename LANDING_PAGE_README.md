# Maya AI - Glassmorphism Landing Page

A stunning, modern landing page for Maya AI built with React and featuring beautiful glassmorphism effects, smooth animations, and responsive design.

## ✨ Features

### 🎨 **Modern Glassmorphism Design**
- **Dark gradient background** with animated grid pattern
- **Floating animated stars** with pulse effects and glow
- **Semi-transparent glass panels** with backdrop blur effects
- **Gradient text effects** and smooth color transitions

### 🚀 **Interactive Elements**
- **Floating navigation bar** with smooth scroll-to-section functionality
- **Animated hero section** with pulsing glow effects
- **Interactive chat demo** showcasing Maya AI conversation
- **Feature cards** with hover animations and scaling effects
- **Social media buttons** with glow and transform effects

### 📱 **Responsive Design**
- **Mobile-first approach** with collapsible hamburger menu
- **Adaptive layouts** for desktop, tablet, and mobile
- **Touch-friendly buttons** and optimized spacing
- **Smooth animations** across all device sizes

### 🎭 **Advanced Animations**
- **Framer Motion integration** for smooth page transitions
- **Scroll-triggered animations** using Intersection Observer
- **Floating stars** with randomized movement patterns
- **Background gradient animations** with color shifting
- **Hover effects** with scale, glow, and transform animations

### 🔐 **Authentication Integration**
- **Popup modal system** for login/signup (no page navigation)
- **Glassmorphism auth forms** matching the landing page design
- **Real-time form validation** with checkmark indicators
- **Social login buttons** with smooth hover effects

## 🛠️ **Technical Implementation**

### **Components Created**
1. **LandingPage.js** - Main landing page component with sections
2. **AuthModal.js** - Glassmorphism authentication modal
3. **LandingPage.css** - Comprehensive styling with animations
4. **AuthModal.css** - Modal-specific glassmorphism styles

### **Key Libraries Used**
- **React** - Component framework
- **Framer Motion** - Animation library
- **Lucide React** - Modern icon set
- **CSS Custom Properties** - Design system variables

### **Design System**
- **Glassmorphism Variables** - Reusable glass effects
- **Color Palette** - Peach/pink gradient theme
- **Typography Scale** - Consistent font sizing
- **Animation Timings** - Smooth transition system

## 🎯 **Sections Included**

### 1. **Hero Section**
- Large animated title with gradient text
- Subtitle explaining Maya AI's purpose
- Email capture with "Join Beta" CTA button
- Floating heart icon with glow effect

### 2. **Features Section**
- 4 interactive feature cards with icons
- Hover animations and glow effects
- Scroll-triggered fade-in animations
- Glassmorphism card styling

### 3. **Chat Demo Section**
- Interactive chat interface mockup
- Bot and user message bubbles
- Real-time typing simulation
- Glassmorphism chat container

### 4. **Contact Section**
- Social media links with hover effects
- Footer information
- Animated social buttons

### 5. **Floating Navigation**
- Transparent navbar with blur effects
- Smooth scroll to sections
- Mobile hamburger menu
- Authentication buttons

## 🎨 **Color Scheme**

```css
/* Primary Colors */
--primary-gradient: linear-gradient(135deg, #ff6b9d 0%, #ffc3a0 100%)
--background: linear-gradient(135deg, #0a0a0a 0%, #4a3a4a 100%)

/* Glassmorphism */
--glass-background: rgba(26, 15, 26, 0.4)
--glass-border: rgba(255, 255, 255, 0.1)
--glass-shadow: 0 20px 50px rgba(0, 0, 0, 0.4)
```

## 📦 **File Structure**

```
src/
├── components/
│   ├── LandingPage.js          # Main landing page component
│   ├── AuthModal.js            # Authentication popup modal
│   └── ...
├── styles/
│   ├── LandingPage.css         # Landing page styles
│   ├── AuthModal.css           # Auth modal styles
│   ├── variables.css           # Design system variables
│   └── ...
└── ...
```

## 🚀 **Getting Started**

1. **Install Dependencies**
   ```bash
   npm install framer-motion lucide-react
   ```

2. **Import Components**
   ```jsx
   import LandingPage from './components/LandingPage';
   import './styles/LandingPage.css';
   ```

3. **Use in App**
   ```jsx
   function App() {
     return <LandingPage />;
   }
   ```

## 🎭 **Animation Features**

- **Page Load**: Hero section slides up with fade-in
- **Scroll Animations**: Elements animate in when scrolled into view
- **Hover Effects**: Cards, buttons, and icons scale and glow on hover
- **Background**: Floating stars and gradient animations
- **Navigation**: Smooth scroll to sections with easing
- **Mobile**: Hamburger menu with slide animations

## 📱 **Responsive Breakpoints**

- **Desktop**: 1024px+ (full layout)
- **Tablet**: 768px-1024px (adjusted spacing)
- **Mobile**: 480px-768px (stacked layout)
- **Small Mobile**: <480px (compact design)

## 🔧 **Customization**

### **Colors**
Update the CSS custom properties in `variables.css` to change the color scheme.

### **Content**
Modify the text, images, and chat messages in `LandingPage.js`.

### **Animations**
Adjust Framer Motion variants and CSS keyframes for different animation styles.

### **Sections**
Add or remove sections by modifying the component structure.

## 🌟 **Browser Support**

- **Chrome**: Full support with backdrop-filter
- **Firefox**: Full support 
- **Safari**: Full support with -webkit-backdrop-filter
- **Edge**: Full support

## 📄 **License**

Built for Maya AI project. All rights reserved.

---

**Built with ❤️ using React, Framer Motion, and modern CSS**