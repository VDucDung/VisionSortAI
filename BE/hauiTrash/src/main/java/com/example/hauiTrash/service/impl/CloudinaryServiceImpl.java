package com.example.hauiTrash.service.impl;
import com.cloudinary.Cloudinary;
import com.cloudinary.utils.ObjectUtils;
import com.example.hauiTrash.service.CloudinaryService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import javax.imageio.ImageIO;
import java.io.ByteArrayInputStream;
@Service
@RequiredArgsConstructor
public class CloudinaryServiceImpl implements CloudinaryService {
    private final Cloudinary cloudinary;
    @Override public String uploadImage(MultipartFile file) {
        if (file.isEmpty()) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Vui lòng chọn ảnh");
        if (file.getSize() > 10 * 1024 * 1024) throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE, "Ảnh vượt quá 10 MB");
        byte[] bytes;
        try {
            bytes = file.getBytes();
            try (var input = ImageIO.createImageInputStream(new ByteArrayInputStream(bytes))) {
                var readers = ImageIO.getImageReaders(input);
                if (!readers.hasNext()) throw new IllegalArgumentException();
                var reader = readers.next();
                try {
                    reader.setInput(input);
                    String format = reader.getFormatName();
                    if (!(format.equalsIgnoreCase("png") || format.equalsIgnoreCase("jpeg") || format.equalsIgnoreCase("webp"))) throw new IllegalArgumentException();
                    int width = reader.getWidth(0), height = reader.getHeight(0);
                    if (width <= 0 || height <= 0 || width > 8192 || height > 8192 || (long) width * height > 12_000_000) throw new IllegalArgumentException();
                    // Decode only after bounding dimensions; headers/extensions alone do not prove a valid image.
                    if (reader.read(0) == null) throw new IllegalArgumentException();
                } finally { reader.dispose(); }
            }
        } catch (Exception invalid) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Ảnh cần là JPG/PNG/WebP hợp lệ, tối đa 12 megapixel và cạnh dài nhất 8192 px");
        }
        try {
            var uploaded = cloudinary.uploader().upload(bytes, ObjectUtils.asMap("folder", "hauitrash/originals", "resource_type", "image"));
            return uploaded.get("secure_url").toString();
        } catch (Exception unavailable) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Không thể lưu ảnh. Hãy kiểm tra cấu hình Cloudinary và kết nối mạng.");
        }
    }
}
