from rest_framework.response import Response
from rest_framework import viewsets,status
from django.views.decorators.csrf import csrf_exempt
from .models import *
from api.models import Movie
from .serializers import *
from rest_framework.authtoken.models import Token
from django.contrib.auth import login,logout,authenticate
from django.contrib.auth.hashers import check_password
from django.db.models import F
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from oauth2_provider.views import ProtectedResourceView
import requests
from django.core.exceptions import ObjectDoesNotExist
import random 
import string

class UserViewSet(viewsets.ViewSet):
    lookup_field = 'username' # overrides the default field to look for in retrieve, the default is pk 
    serializer_class = UserSerializer
    def list(self, request):
        queryset = User.objects.all()
        serializer = self.serializer_class(queryset, many =True)
        return Response(serializer.data)

    def create(self ,request):
        new_user = request.data
        if User.objects.filter(email = new_user['email']).exists():
            return Response({"error":"Email already used"}, status=status.HTTP_403_FORBIDDEN)
        if User.objects.filter(username = new_user['username']).exists():
            while {'username':new_user['username']} in User.objects.values('username'):
                usernamee = new_user['username']+ " #"+str(random.randrange(1000,99999))
                new_user['username'] =usernamee
                print(new_user['username'])
        new_user['pfp'] = None
        user =User.objects.create_user(username = new_user["username"], email=new_user["email"], password = new_user["password"],pfp=new_user["pfp"])
        token = Token.objects.create(user = user)
        authuser = authenticate(email = new_user['email'], password =new_user['password'])
        if authuser is not None :
            return Response({"user" : self.serializer_class(user).data, "token" : token.key}, status=status.HTTP_201_CREATED)
        else : 
            return Response({"error":"Can't register , check your credentials !"}, status = status.HTTP_400_BAD_REQUEST)
    def retrieve(self, request, username=None):
        try :
            user = User.objects.get(username = username)
            serializer = self.serializer_class(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except :
            return Response("Not Found" , status= status.HTTP_404_NOT_FOUND)

class googleLoginViewSet(viewsets.ViewSet):
    def create(self, request):
        email= request.data["email"]
        try :
            user = User.objects.get(email = email)
        except ObjectDoesNotExist:
            return Response({"error": "Wrong email or password 1 !"}, status= status.HTTP_404_NOT_FOUND)
        token = Token.objects.get_or_create(user=user)[0]
        return Response({"user" :UserSerializer(user).data, "token" : token.key},status=status.HTTP_302_FOUND)


class LoginViewSet(viewsets.ViewSet):
    def create(self , request):
        email = request.data["email"]
        password = request.data["password"]
        try :
            user = User.objects.get(email = email)
        except ObjectDoesNotExist:
            return Response({"error": "Wrong email or password 1 !"}, status= status.HTTP_404_NOT_FOUND)
        if not check_password(password, user.password) :
            return Response({"error": "Wrong email or password 2 !"}, status= status.HTTP_404_NOT_FOUND)
        token = Token.objects.get_or_create(user = user)[0]
       
        return Response({"user" :UserSerializer(user).data, "token" : token.key},status=status.HTTP_302_FOUND)

class LogoutViewSet(viewsets.ViewSet):
    permission_classes =[IsAuthenticated]
    def create(self, request):
        request.user.auth_token.delete()
        return Response({"error":"user logged out"})

class TokenValidate(APIView):
    def get(self, request, *args, **kwargs):
        client_id = "798671795051-c95amd54jght2rvvkbnqog71ilut2kch.apps.googleusercontent.com"
        access_token = request.headers.get("Authorization",None)
        if access_token is None :
            return Response({"error" :"Access token missing"}, status=status.HTTP_403_FORBIDDEN)
        access_token = access_token.split(" ")[1]
        token_info = requests.get(f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={access_token}").json()
        if int(token_info["expires_in"]) <= 0 :
            return Response({"error":"access token expired"}, status=status.HTTP_401_UNAUTHORIZED)
        if token_info["aud"] != client_id :
            return Response({"error":"wrong access token"}, status=status.HTTP_401_UNAUTHORIZED)
        user_info = requests.get(f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={access_token}").json()
        if token_info["sub"] != user_info["sub"]: # to ensure that the user info return belong to the user's token 
            return Response({"error":"wrong user"}, status=status.HTTP_401_UNAUTHORIZED)
        user_data = {"email":user_info["email"], "username":user_info["name"],"password":passwordGenerate()}
        try :
            user = User.objects.get(email = user_data["email"]) 
            response = requests.post("http://127.0.0.1:8000/glogin/", json=user_data).json()
            return Response(response,status=status.HTTP_200_OK)
        except ObjectDoesNotExist :
            response = requests.post("http://127.0.0.1:8000/users/", json=user_data).json()
            return Response(response,status=status.HTTP_201_CREATED)
           
def passwordGenerate():
    password=""
    while len(password) < 20:
        password += random.choice(string.printable)
    return password


class CommentReplyApiView(APIView) :
    permission_classes= [IsAuthenticated]
    def post(self, request):
        is_reply =  request.data["reply"]
        print(request.data)
        movie = Movie.objects.get(pk = request.data['page_id'])
        if (is_reply) :
            data= {
                "user":User.objects.get(pk = Token.objects.get(key = request.headers["Authorization"].split(" ")[1]).user_id).id,
                "text": request.data["text"],
                "date":request.data["dateAdded"],
                "parent_comment":Comments.objects.get(pk=request.data['id_replying_to']).id,
                "user_replying_to":User.objects.get(username= request.data["username_replying_to"]).id,
                "movie_page": request.data["page_id"]
            }
            reply = ReplySerializer(data=data)
            if reply.is_valid():
                reply.save()
                movie.commentsNumber = F('commentsNumber') + 1
                movie.save(update_fields=['commentsNumber'])
                movie.refresh_from_db()

            else:
                print(reply.errors)
                return Response({"error":"bad request"},status=status.HTTP_400_BAD_REQUEST)
            comments_count =movie.commentsNumber
            profile= User.objects.get(username=reply.data['user']).pfp.url if User.objects.get(username=reply.data['user']).pfp else User.objects.get(username = reply.data["user"]).username[0].upper()
            return Response({"data":reply.data,"pfp":profile,"comments_count":str(comments_count)},status=status.HTTP_200_OK)
        else :
            data= {
                "user":User.objects.get(pk = Token.objects.get(key = request.headers["Authorization"].split(" ")[1]).user_id).id,
                "text": request.data["text"],
                "date":request.data["dateAdded"],
                "movie_page": request.data["page_id"]
            }
            comment = CommentSerializer(data=data)
            movie = Movie.objects.get(pk = request.data['page_id'])
            if comment.is_valid():
                comment.save()
                movie.commentsNumber = F('commentsNumber') + 1
                movie.save(update_fields=['commentsNumber'])
                movie.refresh_from_db()
            else:
                print(comment.errors)
                return Response({"error":"bad request"},status=status.HTTP_400_BAD_REQUEST)
            profile= User.objects.get(pk=comment.data['user']).pfp.url if User.objects.get(pk=comment.data['user']).pfp else User.objects.get(pk = comment.data["user"]).username[0].upper()
            comments_count =movie.commentsNumber

            return Response({"data":comment.data,"pfp":str(profile),"comments_id":Comments.objects.count(),"comments_count":str(comments_count)},status = status.HTTP_200_OK)

class AllComents(APIView):
    permission_classes = [IsAuthenticated]
    def get(self,request):
        comments = Comments.objects.all().order_by("-date")
        commentsSerializer = CommentReplySerializer(comments,many=True)
        return Response(commentsSerializer.data,status=status.HTTP_200_OK)
    def post(self, request):
        try :
            movie =  Movie.objects.get(pk=request.data["page_id"])
            comments = Comments.objects.filter(movie_page =movie.id).order_by("-date")
            commentsSerializer = CommentReplySerializer(comments,many=True)
            comments_count =movie.commentsNumber
            return Response({"comments":commentsSerializer.data,"latest_id":Replies.objects.count(),"comments_id":Comments.objects.count(),"comments_count":comments_count},status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({"error":"No comments Yet !","comments_id":Comments.objects.count()},status=status.HTTP_204_NO_CONTENT)

class LikesView(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self,request):
        user = Token.objects.get(key= request.headers["Authorization"].split(" ")[1]).user
        comment = Comments.objects.get(id=request.data["id"]) if not request.data["reply"] else Replies.objects.get(id = request.data["id"])
        UserCommentInstance ,created= CommentsLikesDislike.objects.get_or_create(user= user,comment=comment,defaults={
        "liked":True,"disliked":False
        }) if not request.data["reply"] else RepliesLikesDislike.objects.get_or_create(user= user,reply=comment,defaults={
        "liked":True,"disliked":False
        })
        if created :
            comment.likes = F("likes") +1
            comment.save(update_fields=["likes"])
            comment.refresh_from_db()

        else :
            if UserCommentInstance.disliked == True :
                UserCommentInstance.disliked = False
                UserCommentInstance.liked =  True
                UserCommentInstance.save(update_fields=["disliked","liked"])
                comment.dislikes = F("dislikes") - 1
                comment.likes = F("likes") + 1
                comment.save(update_fields=["dislikes","likes"])
                comment.refresh_from_db()
            else :
                UserCommentInstance.liked = True if not UserCommentInstance.liked else False
                UserCommentInstance.save(update_fields=["liked",])
                comment.likes = F("likes") + 1 if UserCommentInstance.liked else F("likes")-1 
                comment.save(update_fields=["likes"])
                comment.refresh_from_db()

        return Response({"likes":str(comment.likes),"dislikes":str(comment.dislikes)}, status=status.HTTP_200_OK)

class DislikesView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self,request):
        user = Token.objects.get(key= request.headers["Authorization"].split(" ")[1]).user
        comment = Comments.objects.get(id=request.data["id"]) if not request.data["reply"] else Replies.objects.get(id = request.data["id"])
        UserCommentInstance ,created= CommentsLikesDislike.objects.get_or_create(user= user,comment=comment,defaults={
        "liked":False,"disliked":True
        }) if not request.data["reply"] else RepliesLikesDislike.objects.get_or_create(user= user,reply=comment,defaults={
        "liked":False,"disliked":True
        })
        if created :
            comment.dislikes = F("dislikes") +1
            comment.save(update_fields=["dislikes"]) #update the instance , but it still contain outdated data
            comment.refresh_from_db() #refresh the instance from the database to get the updated latest data

        else :
            if UserCommentInstance.liked == True :
                UserCommentInstance.liked = False
                UserCommentInstance.disliked =  True
                UserCommentInstance.save(update_fields=["disliked","liked"])
                comment.likes = F("likes") - 1
                comment.dislikes = F("dislikes") + 1
                comment.save(update_fields=["dislikes","likes"])
                comment.refresh_from_db()
            else :
                UserCommentInstance.disliked = True if not UserCommentInstance.disliked else False
                UserCommentInstance.save(update_fields=["disliked",])
                comment.dislikes = F("dislikes") + 1 if UserCommentInstance.disliked else F("dislikes")-1 
                comment.save(update_fields=["dislikes"])
                comment.refresh_from_db()
        return Response({"likes":str(comment.likes),"dislikes":str(comment.dislikes)}, status=status.HTTP_200_OK)

class GetLikesDislikesView(APIView):
    def post(self,request):
        comment = Comments.objects.get(id=request.data["id"]) if not request.data["reply"] else Replies.objects.get(id = request.data["id"])
        likes = comment.likes
        dislikes = comment.dislikes
        return Response({"likes":likes,"dislikes":dislikes}, status=status.HTTP_200_OK)
        
