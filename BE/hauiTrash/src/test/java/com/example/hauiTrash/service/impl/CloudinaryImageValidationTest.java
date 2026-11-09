package com.example.hauiTrash.service.impl;

import com.cloudinary.Cloudinary;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class CloudinaryImageValidationTest {
    private final Cloudinary cloud = mock(Cloudinary.class);
    private final CloudinaryServiceImpl service = new CloudinaryServiceImpl(cloud);
    @Test void emptyFileIsRejectedBeforeExternalUpload() {
        var error=assertThrows(ResponseStatusException.class,()->service.uploadImage(new MockMultipartFile("file",new byte[0])));
        assertEquals(400,error.getStatusCode().value()); verifyNoInteractions(cloud);
    }
    @Test void invalidImageCannotBypassValidationWithPngMimeType() {
        var error=assertThrows(ResponseStatusException.class,()->service.uploadImage(new MockMultipartFile("file","fake.png","image/png","not an image".getBytes())));
        assertEquals(400,error.getStatusCode().value()); verifyNoInteractions(cloud);
    }
    @Test void oversizeFileIsRejectedBeforeDecoding() {
        var error=assertThrows(ResponseStatusException.class,()->service.uploadImage(new MockMultipartFile("file",new byte[10*1024*1024+1])));
        assertEquals(413,error.getStatusCode().value()); verifyNoInteractions(cloud);
    }
    private byte[] image(String name) throws Exception {
        try(var stream=getClass().getResourceAsStream("/images/"+name)) {
            assertNotNull(stream);return stream.readAllBytes();
        }
    }
    @Test void jpegPngAndWebpVariantsAreDecodedAndUploadedWithoutChangingTheirBytes() throws Exception {
        var external=mock(Cloudinary.class,RETURNS_DEEP_STUBS);
        when(external.uploader().upload(any(byte[].class),anyMap())).thenReturn(Map.of("secure_url","https://example.com/image"));
        var checked=new CloudinaryServiceImpl(external);
        for(String file:new String[]{"valid.jpg","valid.png","valid-lossy.webp","valid-lossless.webp","valid-alpha.webp"}) {
            byte[] bytes=image(file);
            assertEquals("https://example.com/image",checked.uploadImage(new MockMultipartFile("file",file,"application/octet-stream",bytes)),file);
            verify(external.uploader()).upload(eq(bytes),anyMap());
        }
    }
    @Test void aWebpExtensionOrMimeTypeCannotMakeInvalidDataAnImage() {
        var error=assertThrows(ResponseStatusException.class,()->service.uploadImage(new MockMultipartFile("file","fake.webp","image/webp","not an image".getBytes())));
        assertEquals(400,error.getStatusCode().value());verifyNoInteractions(cloud);
    }
    @Test void truncatedWebpIsRejectedBeforeUpload() throws Exception {
        byte[] bytes=image("truncated.webp");
        var error=assertThrows(ResponseStatusException.class,()->service.uploadImage(new MockMultipartFile("file","broken.webp","image/webp",bytes)));
        assertEquals(400,error.getStatusCode().value());verifyNoInteractions(cloud);
    }
    @Test void unsupportedImageTypesStillCannotBeUploaded() throws Exception {
        byte[] bytes=image("unsupported.gif");
        var error=assertThrows(ResponseStatusException.class,()->service.uploadImage(new MockMultipartFile("file","fake.webp","image/webp",bytes)));
        assertEquals(400,error.getStatusCode().value());verifyNoInteractions(cloud);
    }
}
