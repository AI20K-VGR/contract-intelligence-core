# GLSL Built-in Functions Reference

Complete reference for GLSL ES 1.0 / WebGL functions.

## Trigonometric Functions

| Function | Description | Range |
|----------|-------------|-------|
| `sin(x)` | Sine | [-1, 1] |
| `cos(x)` | Cosine | [-1, 1] |
| `tan(x)` | Tangent | unbounded |
| `asin(x)` | Arc sine | [-PI/2, PI/2] |
| `acos(x)` | Arc cosine | [0, PI] |
| `atan(y, x)` | Arc tangent (quadrant-aware) | [-PI, PI] |
| `atan(y_over_x)` | Arc tangent | [-PI/2, PI/2] |

All accept float, vec2, vec3, vec4. Input in radians.

## Exponential Functions

| Function | Description |
|----------|-------------|
| `pow(x, y)` | x raised to power y |
| `exp(x)` / `exp2(x)` | e^x / 2^x |
| `log(x)` / `log2(x)` | Natural / Base-2 logarithm |
| `sqrt(x)` / `inversesqrt(x)` | Square root / 1/sqrt(x) |

## Common Functions

`mix`, `step`, `smoothstep`, `fract`, `mod`, `clamp` — see SKILL.md's Essential Functions table for the most-used subset.

| Function | Description |
|----------|-------------|
| `abs(x)` / `sign(x)` | Absolute value / -1, 0, or 1 |
| `floor(x)` / `ceil(x)` | Round down / up |
| `min(x, y)` / `max(x, y)` | Minimum / Maximum |

## Geometric Functions

`length`, `distance`, `dot`, `normalize` — see SKILL.md's Essential Functions table for the most-used subset.

| Function | Description |
|----------|-------------|
| `cross(a, b)` | Cross product |
| `reflect(i, n)` / `refract(i, n, eta)` | Reflection / Refraction |

## Vector Relational Functions

`lessThan`, `lessThanEqual`, `greaterThan`, `greaterThanEqual`, `equal`, `notEqual` - Return bvec. `any(bvec)`, `all(bvec)`, `not(bvec)` - Boolean operations.

## Texture Functions

| Function | Description |
|----------|-------------|
| `texture2D(sampler, coord)` | Sample 2D texture |
| `textureCube(sampler, coord)` | Sample cube map |

## Constants

```glsl
#define PI 3.14159265359
#define TWO_PI 6.28318530718
#define HALF_PI 1.57079632679
```

## Type Constructors

```glsl
vec2(x), vec2(x, y)
vec3(x), vec3(xy, z), vec3(x, y, z)
vec4(x), vec4(xyz, w), vec4(xy, zw)
mat2(a, b, c, d), mat3(...), mat4(...)
```

## Operators

```glsl
+  -  *  /           // Arithmetic (component-wise)
<  >  <=  >=  ==  != // Comparison
&&  ||  !            // Logical
mat * mat            // Matrix multiply
mat * vec            // Transform vector
```

## Qualifiers

```glsl
attribute  // Vertex input
uniform    // Constant across draw
varying    // Interpolated vertex->fragment
lowp / mediump / highp  // Precision
in / out / inout / const // Parameters
```

## Built-in Variables

```glsl
// Fragment Shader
vec4 gl_FragCoord;   // Window coordinates
vec4 gl_FragColor;   // Output color (write only)
bool gl_FrontFacing; // Front face?
vec2 gl_PointCoord;  // Point sprite [0,1]

// Vertex Shader
vec4 gl_Position;    // Clip-space position
float gl_PointSize;  // Point size
```
