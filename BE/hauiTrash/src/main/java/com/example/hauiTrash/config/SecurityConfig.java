package com.example.hauiTrash.config;

import com.example.hauiTrash.security.JwtFilter;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.*;

import java.util.List;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true)
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtFilter jwtFilter;
    @org.springframework.beans.factory.annotation.Value("${app.cors.origins:http://localhost:*,http://127.0.0.1:*}")
    private String allowedOrigins;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {

        http
                .csrf(csrf -> csrf.disable())
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

                .formLogin(form -> form.disable())
                .httpBasic(basic -> basic.disable())
                .requestCache(cache -> cache.disable())
                .logout(logout -> logout.disable())

                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint((request, response, authException) -> {
                            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                            response.setContentType("application/json;charset=UTF-8");
                            response.getWriter().write("{\"message\":\"Unauthorized\"}");
                        })
                        .accessDeniedHandler((request, response, accessDeniedException) -> {
                            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
                            response.setContentType("application/json;charset=UTF-8");
                            response.getWriter().write("{\"message\":\"Forbidden\"}");
                        })
                )

                .authorizeHttpRequests(auth -> auth
                        // Do not turn servlet errors into a new authentication failure.
                        .dispatcherTypeMatchers(jakarta.servlet.DispatcherType.ERROR).permitAll()
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()

                        // ---------- PUBLIC ----------
                        .requestMatchers(HttpMethod.GET, "/api/v1/system/info").permitAll()
                        .requestMatchers("/api/v1/auth/register", "/api/v1/auth/login/user", "/api/v1/auth/login/admin").permitAll()
                        .requestMatchers("/images/**").permitAll()

                        // ---------- ADMIN ----------
                        .requestMatchers("/api/v1/admin/learning", "/api/v1/admin/learning/**").hasRole("ADMIN")
                        .requestMatchers("/api/v1/admin/profile", "/api/v1/admin/profile/password").hasRole("ADMIN")
                        .requestMatchers("/api/v1/admin/statistics", "/api/v1/admin/scans", "/api/v1/admin/users", "/api/v1/admin/users/*").hasRole("ADMIN")


                        // ---------- USER (BẮT BUỘC LOGIN) ----------
                        .requestMatchers("/api/v1/scans", "/api/v1/scans/**", "/api/v1/auth/me", "/api/v1/auth/logout").authenticated()



                        // ---------- ALL OTHER ----------
                        .anyRequest().denyAll()
                )

                .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOriginPatterns(java.util.Arrays.stream(allowedOrigins.split(",")).map(String::trim).toList());
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setExposedHeaders(List.of("Authorization"));
        config.setAllowCredentials(false);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
