#version 120

// Romance of the Three Kingdoms III (DOS) black-bar removal shader.
//
// The game renders 640x400 content centered in a 640x480 mode-12h framebuffer
// (content rows 40..439, black bars rows 0..39 and 440..479).
//
// Behaviour:
//  - Game screens (top 40 rows pure black): crop the bars, map the 640x400
//    content onto the window using PIXEL-PERFECT integer scaling (like
//    DOSBox-X "opengl perfect": the largest integer zoom that fits, centered
//    with black bars), keeping 16:10 square pixels.
//  - Password screen (copy protection; text lives in rows 0..45): show the
//    full 640x480 frame as a centered 4:3 image with pixel-perfect integer
//    scaling, so the screen keeps its original 4:3 aspect.
//  - Any other surface (e.g. DOS text mode 720x400): pass through unchanged.
//
// The window is freely resizable: the game image always keeps its correct
// aspect (16:10 for game screens, 4:3 for the password screen) and is never
// scaled non-integer, so pixels stay crisp at any window size.
//
// Coordinate convention (matches DOSBox-X's own pixel_perfect.glsl):
//   outCoord in [0,1] across the window; the game frame fills the whole
//   texture region; sample uv = gamePixel / rubyTextureSize.

uniform vec2 rubyInputSize;

#if defined(VERTEX)

#if __VERSION__ >= 130
#define COMPAT_VARYING out
#define COMPAT_ATTRIBUTE in
#define COMPAT_TEXTURE texture
#else
#define COMPAT_VARYING varying
#define COMPAT_ATTRIBUTE attribute
#define COMPAT_TEXTURE texture2D
#endif

#ifdef GL_ES
#define COMPAT_PRECISION mediump
#else
#define COMPAT_PRECISION
#endif

COMPAT_ATTRIBUTE vec4 a_position;
COMPAT_VARYING vec2 outCoord;

void main()
{
    gl_Position = a_position;
    outCoord = vec2(a_position.x + 1.0, 1.0 - a_position.y) / 2.0;
}

#elif defined(FRAGMENT)

#if __VERSION__ >= 130
#define COMPAT_VARYING in
#define COMPAT_TEXTURE texture
out vec4 FragColor;
#else
#define COMPAT_VARYING varying
#define FragColor gl_FragColor
#define COMPAT_TEXTURE texture2D
#endif

#ifdef GL_ES
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
#define COMPAT_PRECISION highp
#else
#define COMPAT_PRECISION
#endif

uniform sampler2D rubyTexture;
uniform vec2 rubyTextureSize;
uniform vec2 rubyOutputSize;

COMPAT_VARYING vec2 outCoord;

// Returns true if the top band (source rows 0..~34) contains non-black pixels,
// which is only the case on the password screen.
bool passwordMode()
{
    for (int i = 0; i < 10; i++) {
        float fx = (float(i) + 0.5) / 10.0;
        vec2 uv = vec2(fx * rubyInputSize.x, 5.0) / rubyTextureSize;
        vec3 c = COMPAT_TEXTURE(rubyTexture, uv).rgb;
        if (dot(c, c) > 0.0005) return true;
    }
    return false;
}

void main()
{
    vec2 outpx = outCoord * rubyOutputSize;
    bool is480 = rubyInputSize.y >= 479.5;

    if (is480 && passwordMode()) {
        // Password screen: centered 4:3 region, pixel-perfect integer scale.
        float scale = floor(min(rubyOutputSize.x / 640.0, rubyOutputSize.y / 480.0));
        scale = max(scale, 1.0);
        float regionW = 640.0 * scale;
        float regionH = 480.0 * scale;
        float left = (rubyOutputSize.x - regionW) * 0.5;
        float top = (rubyOutputSize.y - regionH) * 0.5;
        float ox = outpx.x - left;
        float oy = outpx.y - top;
        if (ox < 0.0 || ox > regionW || oy < 0.0 || oy > regionH) {
            FragColor = vec4(0.0, 0.0, 0.0, 1.0);
            return;
        }
        float srcX = ox / regionW * rubyInputSize.x;
        float srcY = oy / regionH * rubyInputSize.y;
        FragColor = COMPAT_TEXTURE(rubyTexture, vec2(srcX, srcY) / rubyTextureSize);
        return;
    }

    if (is480) {
        // Game screen: crop rows 0..39 and 440..479, pixel-perfect 16:10.
        float scale = floor(min(rubyOutputSize.x / 640.0, rubyOutputSize.y / 400.0));
        scale = max(scale, 1.0);
        float regionW = 640.0 * scale;
        float regionH = 400.0 * scale;
        float left = (rubyOutputSize.x - regionW) * 0.5;
        float top = (rubyOutputSize.y - regionH) * 0.5;
        float ox = outpx.x - left;
        float oy = outpx.y - top;
        if (ox < 0.0 || ox > regionW || oy < 0.0 || oy > regionH) {
            FragColor = vec4(0.0, 0.0, 0.0, 1.0);
            return;
        }
        float srcX = ox / regionW * rubyInputSize.x;
        float srcY = 40.0 + oy / regionH * 400.0;
        FragColor = COMPAT_TEXTURE(rubyTexture, vec2(srcX, srcY) / rubyTextureSize);
        return;
    }

    // Other modes: pass through.
    FragColor = COMPAT_TEXTURE(rubyTexture, outCoord * rubyInputSize / rubyTextureSize);
}

#endif
