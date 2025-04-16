import cv2
import numpy as np

class ImageEnhancer:
    @staticmethod
    def apply_unsharp_mask(image, intensity):
        # Convert intensity to parameters (0-100 to reasonable ranges)
        radius = 1.0 + (intensity / 50.0)  # 1.0 to 3.0
        amount = 0.5 + (intensity / 50.0)  # 0.5 to 2.5
        threshold = int(intensity / 10)     # 0 to 10
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(image, (0, 0), radius)
        
        # Create mask
        mask = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)
        
        # Apply threshold to reduce noise
        if threshold > 0:
            low_contrast = np.abs(image - blurred) < threshold
            np.copyto(mask, image, where=low_contrast)
        
        return cv2.convertScaleAbs(mask)

    @staticmethod
    def apply_high_boost(image, intensity):
        # Convert intensity to boost factor (1.0 to 3.0)
        boost_factor = 1.0 + (intensity / 50.0)
        
        # Create sharpening kernel
        kernel = np.array([[-1, -1, -1],
                         [-1,  8 + boost_factor, -1],
                         [-1, -1, -1]]) / (boost_factor + 1)
        
        # Apply high-boost filter
        sharpened = cv2.filter2D(image, -1, kernel)
        
        # Combine with original image
        result = cv2.addWeighted(image, 1.0, sharpened, 0.5, 0)
        return cv2.convertScaleAbs(result)

    @staticmethod
    def apply_laplacian(image, intensity):
        intensity_scale = intensity / 50.0
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        laplacian = cv2.convertScaleAbs(laplacian)
        enhanced = cv2.addWeighted(image, 1.0, laplacian, intensity_scale, 0)
        return cv2.convertScaleAbs(enhanced)

    @staticmethod
    def apply_sobel(image, intensity):
        scale = intensity / 50
        sobelx = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
        gradient = np.sqrt(sobelx**2 + sobely**2) * scale
        return np.uint8(gradient)

    @staticmethod
    def apply_prewitt(image, intensity):
        scale = intensity / 50
        kernelx = np.array([[1,1,1],[0,0,0],[-1,-1,-1]]) * scale
        kernely = np.array([[-1,0,1],[-1,0,1],[-1,0,1]]) * scale
        prewittx = cv2.filter2D(image, -1, kernelx)
        prewitty = cv2.filter2D(image, -1, kernely)
        return cv2.addWeighted(prewittx, 0.5, prewitty, 0.5, 0)

    @staticmethod
    def apply_gaussian_blur(image, intensity):
        ksize = int(1 + (intensity // 10) * 2)  # odd kernel size
        if ksize < 3:
            ksize = 3
        return cv2.GaussianBlur(image, (ksize, ksize), 0)

    @staticmethod
    def apply_median_blur(image, intensity):
        ksize = int(1 + (intensity // 10) * 2)
        if ksize < 3:
            ksize = 3
        return cv2.medianBlur(image, ksize)

    @staticmethod
    def apply_emboss(image, intensity):
        kernel = np.array([[ -2, -1, 0],
                           [ -1, 1, 1],
                           [ 0, 1, 2]]) * (intensity / 50)
        embossed = cv2.filter2D(image, -1, kernel) + 128
        return cv2.convertScaleAbs(embossed)

    @staticmethod
    def apply_sepia(image, intensity):
        img = image.astype(np.float64)
        sepia_filter = np.array([[0.393, 0.769, 0.189],
                                 [0.349, 0.686, 0.168],
                                 [0.272, 0.534, 0.131]])
        sepia_img = cv2.transform(img, sepia_filter)
        sepia_img = np.clip(sepia_img, 0, 255)
        alpha = intensity / 100.0
        blended = cv2.addWeighted(img, 1 - alpha, sepia_img, alpha, 0)
        return blended.astype(np.uint8)

    @staticmethod
    def apply_invert(image, intensity):
        alpha = intensity / 100.0
        inverted = 255 - image
        return cv2.addWeighted(image, 1 - alpha, inverted, alpha, 0).astype(np.uint8)

    @staticmethod
    def apply_box_blur(image, intensity):
        ksize = int(1 + (intensity // 10) * 2)
        if ksize < 3:
            ksize = 3
        return cv2.blur(image, (ksize, ksize))

    @staticmethod
    def apply_bilateral_filter(image, intensity):
        d = 5 + int(intensity // 10)
        sigmaColor = 75 + intensity
        sigmaSpace = 75 + intensity
        return cv2.bilateralFilter(image, d, sigmaColor, sigmaSpace)

    @staticmethod
    def apply_cartoon(image, intensity):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 7)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                      cv2.THRESH_BINARY, 9, 9)
        color = cv2.bilateralFilter(image, 9, 250, 250)
        cartoon = cv2.bitwise_and(color, color, mask=edges)
        return cartoon

    @staticmethod
    def apply_pencil_sketch(image, intensity):
        gray, color = cv2.pencilSketch(image, sigma_s=60, sigma_r=0.07, shade_factor=0.05 + intensity/1000)
        return color

    @staticmethod
    def apply_canny(image, intensity):
        lower = max(0, int(50 - intensity/2))
        upper = min(255, int(150 + intensity))
        edges = cv2.Canny(image, lower, upper)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def apply_threshold(image, intensity):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, intensity, 255, cv2.THRESH_BINARY)
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def apply_clahe(image, intensity):
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0 + intensity/50, tileGridSize=(8,8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl,a,b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

    @staticmethod
    def enhance(image, method='unsharp_mask', intensity=50, mask=None):
        methods = {
            'unsharp_mask': ImageEnhancer.apply_unsharp_mask,
            'high_boost': ImageEnhancer.apply_high_boost,
            'laplacian': ImageEnhancer.apply_laplacian,
            'sobel': ImageEnhancer.apply_sobel,
            'prewitt': ImageEnhancer.apply_prewitt,
            'gaussian_blur': ImageEnhancer.apply_gaussian_blur,
            'median_blur': ImageEnhancer.apply_median_blur,
            'emboss': ImageEnhancer.apply_emboss,
            'sepia': ImageEnhancer.apply_sepia,
            'invert': ImageEnhancer.apply_invert,
            'box_blur': ImageEnhancer.apply_box_blur,
            'bilateral_filter': ImageEnhancer.apply_bilateral_filter,
            'cartoon': ImageEnhancer.apply_cartoon,
            'pencil_sketch': ImageEnhancer.apply_pencil_sketch,
            'canny': ImageEnhancer.apply_canny,
            'threshold': ImageEnhancer.apply_threshold,
            'clahe': ImageEnhancer.apply_clahe
        }
        # Remove selective_blur logic
        if method not in methods:
            raise ValueError(f"Method {method} not supported")
        return methods[method](image, intensity)