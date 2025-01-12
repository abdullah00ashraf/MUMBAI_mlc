/**
 * SENTINEL V7 - TRACK BETA: C++/IoT EDGE IDENTITY
 * Component: Quantum-Resistant Edge Attestation (ESP32 / IoT Node)
 * 
 * Objective: Implement AES-256-GCM encryption with Auth Tag generation
 * for raw physical inputs to prevent "Ghost Rain" injection attacks.
 */

#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <sstream>
#include <iomanip>

// OpenSSL for AES-256-GCM and Base64
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <openssl/bio.h>
#include <openssl/buffer.h>

class EdgeIdentityManager {
private:
    // 256-bit Hardcoded Data Encryption Key (DEK) for Node (32 bytes)
    unsigned char dek[32] = {
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10,
        0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
        0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20
    };

    std::string base64_encode(const unsigned char* buffer, size_t length) {
        BIO *bio, *b64;
        BUF_MEM *bufferPtr;

        b64 = BIO_new(BIO_f_base64());
        bio = BIO_new(BIO_s_mem());
        bio = BIO_push(b64, bio);

        BIO_set_flags(bio, BIO_FLAGS_BASE64_NO_NL); // Ignore newlines
        BIO_write(bio, buffer, length);
        BIO_flush(bio);
        BIO_get_mem_ptr(bio, &bufferPtr);
        BIO_set_close(bio, BIO_NOCLOSE);

        std::string result(bufferPtr->data, bufferPtr->length);
        BUF_MEM_free(bufferPtr);
        BIO_free_all(bio);

        return result;
    }

public:
    EdgeIdentityManager() {}

    /**
     * Constructs JSON payload, encrypts it via AES-256-GCM, 
     * and returns the Base64 of (IV + Ciphertext + AuthTag).
     */
    std::string build_and_encrypt_payload(double lat, double lon, double water_depth_mm, long timestamp) {
        // 1. Build JSON Payload
        std::stringstream ss;
        ss << "{\"latitude\":" << std::fixed << std::setprecision(6) << lat 
           << ",\"longitude\":" << lon 
           << ",\"water_depth_mm\":" << std::setprecision(2) << water_depth_mm 
           << ",\"timestamp\":" << timestamp << "}";
        
        std::string plaintext = ss.str();
        std::cout << "[DEBUG] Plaintext JSON: " << plaintext << std::endl;

        // 2. Generate 12-byte IV (Nonce)
        unsigned char iv[12];
        if (!RAND_bytes(iv, sizeof(iv))) {
            throw std::runtime_error("Failed to generate random IV.");
        }

        // 3. Setup AES-256-GCM Encryption
        EVP_CIPHER_CTX *ctx;
        int len;
        int ciphertext_len;
        
        unsigned char ciphertext[1024]; // Safe buffer size for this payload
        unsigned char tag[16];

        if(!(ctx = EVP_CIPHER_CTX_new())) throw std::runtime_error("Failed to create CTX");

        if(1 != EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL))
            throw std::runtime_error("Failed to init encryption");

        // Set IV length (default is 12)
        if(1 != EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, 12, NULL))
            throw std::runtime_error("Failed to set IV length");

        // Init key and IV
        if(1 != EVP_EncryptInit_ex(ctx, NULL, NULL, dek, iv))
            throw std::runtime_error("Failed to init DEK and IV");

        // Encrypt message
        if(1 != EVP_EncryptUpdate(ctx, ciphertext, &len, (unsigned char*)plaintext.c_str(), plaintext.length()))
            throw std::runtime_error("Failed to encrypt update");
        ciphertext_len = len;

        // Finalize encryption
        if(1 != EVP_EncryptFinal_ex(ctx, ciphertext + len, &len))
            throw std::runtime_error("Failed to finalize encryption");
        ciphertext_len += len;

        // Get the Auth Tag
        if(1 != EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, 16, tag))
            throw std::runtime_error("Failed to get auth tag");

        EVP_CIPHER_CTX_free(ctx);

        // 4. Concatenate IV + Ciphertext + Tag
        std::vector<unsigned char> final_payload;
        final_payload.insert(final_payload.end(), iv, iv + 12);
        final_payload.insert(final_payload.end(), ciphertext, ciphertext + ciphertext_len);
        final_payload.insert(final_payload.end(), tag, tag + 16);

        // 5. Base64 Encode
        return base64_encode(final_payload.data(), final_payload.size());
    }
};

int main() {
    EdgeIdentityManager edge;

    std::cout << "--- Sentinel V7 Track Beta: Edge Attestation Matrix ---" << std::endl;
    std::cout << "Hardware Security Module: AES-256-GCM Initialization" << std::endl;
    
    // Physical inputs
    double latitude = 18.9220;
    double longitude = 72.8347;
    double water_depth_mm = 450.5; // High flood depth
    
    auto now = std::chrono::system_clock::now();
    long timestamp = std::chrono::duration_cast<std::chrono::seconds>(now.time_since_epoch()).count();

    try {
        std::string secure_payload = edge.build_and_encrypt_payload(latitude, longitude, water_depth_mm, timestamp);
        
        std::cout << "[POST] Secure Payload Generated for Transmission:" << std::endl;
        std::cout << "Payload (Base64 IV+Cipher+Tag): " << secure_payload << std::endl;
        
        // Output formatted for HTTP transmission
        std::cout << "\nHTTP POST /api/v1/telemetry/iot-ingest" << std::endl;
        std::cout << "Content-Type: text/plain" << std::endl;
        std::cout << "\n" << secure_payload << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "Encryption Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
