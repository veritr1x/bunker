#include <GLES3/gl31.h>
void mx_active(GLuint p,GLuint i,GLsizei n,GLsizei*l,GLint*s,GLenum*t,GLchar*out){glGetActiveAttrib(p,i,n,l,s,t,out);}
GLint mx_location(GLuint p,const GLchar*n){return glGetAttribLocation(p,n);}
void mx_precision(GLenum s,GLenum t,GLint*r,GLint*p){glGetShaderPrecisionFormat(s,t,r,p);}
void mx_source(GLuint s,GLsizei n,GLsizei*l,GLchar*out){glGetShaderSource(s,n,l,out);}
void mx_vertex(GLuint i,GLenum p,GLint*out){glGetVertexAttribiv(i,p,out);}
void mx_bind(GLuint p,GLuint i,const GLchar*n){glBindAttribLocation(p,i,n);}
void mx_blend(GLenum e){glBlendEquation(e);}
void mx_stencil(GLuint v){glStencilMask(v);}
void mx_validate(GLuint p){glValidateProgram(p);}
void mx_vertex4f(GLuint i,GLfloat x,GLfloat y,GLfloat z,GLfloat w){glVertexAttrib4f(i,x,y,z,w);}
void mx_vertex4f_indirect(GLuint i,GLfloat x,GLfloat y,GLfloat z,GLfloat w){PFNGLVERTEXATTRIB4FPROC volatile fn=glVertexAttrib4f;fn(i,x,y,z,w);}
void mx_vertex4fv(GLuint i,const GLfloat*v){glVertexAttrib4fv(i,v);}
