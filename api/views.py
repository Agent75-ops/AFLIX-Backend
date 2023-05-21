from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import generics, viewsets
from rest_framework.response import Response
from rest_framework import status
import requests
from .serializers import *
from .models import *
from django.core.exceptions import ObjectDoesNotExist
from datetime import date
import threading
from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q 

# Create your views here.
ImdbApiKey = "k_ofu8b6bo"

def SaveData(Apidata):
    url = f"http://www.omdbapi.com/?apikey=b6661a6a&i={Apidata['id']}"
    omdbCall = requests.get(url).json()
    if omdbCall['Response'] == 'False':
        add_to_omdb = ["Director","Plot","Runtime","Released","Poster","imdbRating","Genre"]
        for i in add_to_omdb :
            omdbCall[i]= "N/A" #if omdbCall is False, add these to it and set them 'N/A'
    dir = Apidata["crew"].split(",")[0].replace("(dir.)",'') if 'crew' in Apidata else Apidata["directors"] 
    if dir == None:
        dir = omdbCall["Director"]
    dir = dir.split(",")[0] if ',' in dir else dir
    director, created = Directors.objects.get_or_create(name = dir) #create the director if not found else get it 
    genreList = []
    response_genre =Apidata["genres"].split(", ") if 'genres' in Apidata else omdbCall["Genre"].split(", ") # get genre list 
    for genre in response_genre:
        try :
            Genre.objects.get(name=genre) # if the genre is not in the db, add it to another list of dictionaries(genreList)
        except ObjectDoesNotExist:
            genreList += [{"name":genre}]
    if len(genreList) >0 : # check if there is genre to be added to the db 
        genres = GenresSerializer(data=genreList,many=True)
        if genres.is_valid():
            genres.save() # save the genres to the db the need to be added 
    try :
        Movie.objects.get(title = Apidata["title"]) # check if the the movie is in the db .
    # if it doesn't get the genres ids and director id of it + all the other data from the omdb and imdb api calls
    except Exception as e: 
       
        genres_ = Genre.objects.filter(name__in =response_genre) 
        director = Directors.objects.get(name=dir)
        genres_id = [genre.id for genre in genres_]
        meta =''
        if "metacriticRating" in Apidata : #check in which api meta score is available and save it in meta variable
            meta = Apidata["metacriticRating"]
        elif "Metascore" in omdbCall:
            meta = omdbCall["Metascore"]
        try:
            float(meta) # if meta is not a number , set it to "N/A"
        except (ValueError,TypeError):
            meta="N/A"
        #check in which api plot is available and save it in plot variable
        plot = omdbCall["Plot"] if ("plot" not in Apidata or Apidata["plot"] == None) else Apidata['plot']
        if len(plot) ==0 : #if the value of plot is 0, set it to none, in apis it could be empty string.
            plot="N/A"
        #check in which api runtime is available and save it in duration variable
        duration= omdbCall["Runtime"] if ("runtimeMins" not in Apidata or Apidata["runtimeMins"] == None) else Apidata["runtimeMins"]
        duration= duration.split(' ')[0]
        try:
            int(duration) #if duration is not a number , set it to "N/A"
        except (ValueError,TypeError):
            duration=0
        #check in which api released is available and save it in released variable
        released = omdbCall["Released"] if ("releaseState" not in Apidata or Apidata["releaseState"] == None) else Apidata["releaseState"]
        #check in which api content rate is available and save it in rating variable
        if "contentRating" not in Apidata :
            rating = (omdbCall["Rated"] if "Rated" in omdbCall else "N/A")
        else:
            rating=Apidata["contentRating"]
        #check in which api imdb rating is available and save it in imdb variable
        imdb = omdbCall["imdbRating"] if ("imDbRating" not in Apidata or Apidata["imDbRating"] == "null") else Apidata["imDbRating"]
        try :
            float(imdb)#if imdb is not a number ,set it to "N/A"
        except (ValueError,TypeError) :
            imdb="N/A"
        if "Poster" not in omdbCall or omdbCall["Poster"] =="N/A": # if theres no poster in omdb api
            url = f"http://www.omdbapi.com/?apikey=b6661a6a&t={Apidata['title']}"#send a request to another endpoint to get the poster
            new_omdbCall = requests.get(url).json()
            # check if the call succeeds and the poster is available save it in a variable
            if  new_omdbCall['Response'] != 'False' and new_omdbCall["Poster"] !="N/A" : 
                    poster = new_omdbCall["Poster"]
            else :
                poster = Apidata["image"]
        else : # if the poster is already available, save it in poster variable
            poster = omdbCall["Poster"]
        if poster =="N/A" or poster==None: # if the poster is not available , set it to a default poster
            poster = "https://imdb-api.com/images/128x176/nopicture.jpg"
        # get the trailer and the thumbnail of a movie from another endpoint
        trailerCall = requests.get(f"https://imdb-api.com/en/API/Trailer/{ImdbApiKey}/{Apidata['id']}").json()
        if trailerCall['errorMessage'] =="":
        
            trailer = trailerCall["linkEmbed"] 
            thumbnail = trailerCall["thumbnailUrl"]
        else : 
            trailer = "https://imdb-api.com/images/128x176/nopicture.jpg"
            thumbnail = "https://imdb-api.com/images/128x176/nopicture.jpg"
        # get the image of a movie from another endpoint
        imageCall = requests.get(f"https://imdb-api.com/en/API/Images/{ImdbApiKey}/{Apidata['id']}/Short").json()
        if imageCall['errorMessage'] =="" and len(imageCall['items'])>1 :
            image = imageCall['items'][1]["image"]
        else : 
            image = "https://imdb-api.com/images/128x176/nopicture.jpg"

        data = {"title":Apidata["title"], # create the data dictionary of all the variables created 
        "trailer":trailer,
        "image":image,
        "thumbnail":thumbnail,
        "imdbId":Apidata['id'],
        "poster":poster,
        "ratings":{"imdb":imdb,"metacritics":meta},
        "plot":plot,
        "contentRate":rating,
        "duration":duration,
        "released":released,
        "genre":genres_id,
        "director":director.pk}
        movieSer = MoviesSerializer(data=data) # create the unexisting movie 
        if movieSer.is_valid():
            movieSer.save()
        else:
            print(movieSer.errors)
            return Response({"error" :movieSer.errors}, status=status.HTTP_404_NOT_FOUND)

def callApi (name): 
    imdburl = f"https://imdb-api.com/en/API/{name}/{ImdbApiKey}" #call the imdb api
    r = requests.get(imdburl).json() #parse the response to json then convert it to dictionary
    if r['errorMessage'] == '' : #check for error messages
        for item in r["items"][:40] :
            SaveData(item)
        return True
    else :
        return False

event = threading.Event() # Create an Event to control the timimg of the thread
def setInterval(func,time,name):
    while True :
        for n in name :
            event.wait(time) # wait for event.set(), if given wait for it then run the function
            result = func(n) # call the function responsible for calling an api at one of the endpoints
            print(result)
        
        
# asign a function to thread, and specify the arguments in args=() parameter (a list of endpoints to call)
thread = threading.Thread(target=setInterval,args=(callApi,10,["InTheaters"]))
# thread.start() # create a separate thread for api requests asynchronously

# InTheaters
class MoviesView(APIView):
    def get(self, request):
        try : 
            movies_names=["Avatar: The Way of Water","Babylon (I)","Strange World","The Fabelmans", 
                        "The Whale","The Menu","Violent Night","The Banshees of Inisherin",
                        "Black Panther: Wakanda Forever"]
            movies_set = Movie.objects.filter(title__in=movies_names)
            MoviesSer = MoviesSerializer(movies_set,many=True) 
            return Response(MoviesSer.data,status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({"error" :str(e)}, status=status.HTTP_404_NOT_FOUND)
        
def get_query_set_with_limit(query_set,start, limit): 
    # if limit is specified as a query string , return limited query set, else query set
    if limit and start:
        try: # check if the limit is a valid int
            limit = int(limit)
            start = int(start)
        except ValueError:
            return None
        if limit <= 0 and start<0:
            return None
        return query_set[start:start+limit]
    if limit :
        try :
            limit = int(limit)
        except ValueError:
            return None
        if limit <= 0:
            return None
        return query_set[:limit]
    return query_set

    
def get_todays_date_iso_format():
    return date.today().isoformat()

def filter_upcoming_movies():
    return (Movie.objects.filter(released__gt = get_todays_date_iso_format()).
           order_by("-released").
           exclude(poster__iendswith="/nopicture.jpg")
    )
def filter_latest_movies():
    return (Movie.objects.filter(released__lte= get_todays_date_iso_format()).
           order_by("-released").
           exclude(poster__iendswith="/nopicture.jpg")
    )
def filter_trending_movies():
    # get a list of dictionaries({ratings__imdb:imdb_rating,pk:pk}) of movies released recently
    movies = Movie.objects.filter(released__lt=get_todays_date_iso_format()).exclude(poster__iendswith="/nopicture.jpg").values("ratings__imdb","pk")
    for movie in movies :
        # convert the imdb rating to a float (ratings is a json fied initially)
        try :
            movie["ratings__imdb"] = float(movie["ratings__imdb"])
        except:
            movie['ratings__imdb'] = 0
    # make a list of all the movies pk's from the movies dictionary where ratings__imdb >= 7 
    movies_filtered_pks = [movie["pk"] for movie in movies if movie["ratings__imdb"] >= 7]
    # get all the movies by the obtained pks
    return Movie.objects.filter(pk__in = movies_filtered_pks)
    

# MostPopularMovies
class TrendingMoviesView(APIView):
    def get(self, request):
            trending_movies_list = filter_trending_movies()
            # check for limit 
            start = request.query_params.get("start")
            limit =request.query_params.get("limit")
            movies = get_query_set_with_limit(trending_movies_list, start,limit)
            if movies is None :
                    return Response({'error':"invalid limit"},status=status.HTTP_400_BAD_REQUEST)
            return Response({"movies":MoviesSerializer(movies, many=True).data},status=status.HTTP_200_OK)
    
class LatestMoviesView(APIView):
    def get(self,request):
            latest_movies_list = filter_latest_movies()
            start = request.query_params.get("start")
            limit =request.query_params.get("limit")
            movies = get_query_set_with_limit(latest_movies_list, start,limit)
            if movies is None :
                return Response({"error":"invalid limit"},status = status.HTTP_400_BAD_REQUEST)
            return Response({"movies":MoviesSerializer(movies, many=True).data}, status=status.HTTP_200_OK)

# ComingSoon
class UpcomingMoviesView(APIView):
    def get(self,request):
  
        # get movies with release date > today
        upcoming_movies_list =filter_upcoming_movies()
        start = request.query_params.get("start")
        limit =request.query_params.get("limit")
        movies = get_query_set_with_limit(upcoming_movies_list, start,limit)
        if movies is None :
            return Response({"error":"invalid limit"},status = status.HTTP_400_BAD_REQUEST)
        return Response({"movies":MoviesSerializer(movies, many=True).data},status=status.HTTP_200_OK)

class SimilarMoviesView(APIView):
    def get(self,request,id=None):
        try:
            movie = Movie.objects.get(pk = id)
        except ObjectDoesNotExist:
            return Response({"error":"movie does not exist"},status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"error":"invalid id"},status=status.HTTP_400_BAD_REQUEST)
        director = movie.director
        genres = movie.genre.all()
        today = date.today().isoformat()
        similar_movies = Movie.objects.filter(Q(Q(genre__in = genres) | Q(director = director))&Q(released__lt =today)).exclude(pk = movie.pk).distinct()
        similar_movies = similar_movies[:15] if len(similar_movies) > 15 else similar_movies
        movies_serializer = MoviesSerializer(similar_movies, many= True)
        return Response({"movies": movies_serializer.data},status=status.HTTP_200_OK)
    

class FavouritesViewSet(viewsets.ModelViewSet):
    queryset=Favorite.objects.all()
    serializer_class = FavouriteSerializer
    lookup_field=['username','movie_id']
    permission_classes=[IsAuthenticated]
    def get_object(self,username,movie_id):
        try: # get a favorite instance using user's username and movie's id instead of favorite id
            return Favorite.objects.get(user=User.objects.get(username=username), movie= Movie.objects.get(pk=movie_id))
        except:
            raise Http404
    def retrieve(self,request,username,movie_id):
        try:
            self.get_object(username,movie_id) # get the favorite instance  using custom get_object()
            return Response({"found":True}, status=status.HTTP_200_OK) # if found send true
        except Http404:
            return Response({"found":False},status=status.HTTP_404_NOT_FOUND)
            
    def create(self, request): #receives a request containing email and movie_id
        user = User.objects.get(email = request.data["email"])
        movie = Movie.objects.get(pk = request.data["movie_id"])
        try :
            fav = Favorite.objects.get(user= user,movie= movie)# get the favorite instance
            fav.delete() # if found delete it (user removed a movie from his favorites)
            return Response({"deleted/created":"deleted"},status=status.HTTP_200_OK)
        except ObjectDoesNotExist: # if the favorite instance doesn't exist
            fav = Favorite.objects.create(user = user, movie=movie) # create it (user added a movie to his favorites)
            return Response({"deleted/created":"created"},status=status.HTTP_200_OK)

class MoviesCountApiView(APIView):
    def get(self, request):
        category = request.query_params.get('category')
        movies = Movie.objects.all()
        if category is not None: 
            
            if category =="trending":
                movies = filter_trending_movies()
            elif category == "upcoming":
                movies = filter_upcoming_movies()
            elif category == "latest":
                movies = filter_latest_movies()
            else :
                return Response({"error":"invalid category"}, status = status.HTTP_400_BAD_REQUEST)
        movies_count = movies.count()
        return Response({"movies_count":movies_count},status = status.HTTP_200_OK)

class MovieListApiView(generics.ListAPIView):
    queryset = Movie.objects.all()
    serializer_class = MoviesSerializer
    def get_queryset(self, limit=None):
        if limit is not None :
            return Movie.objects.all()[:limit]
        return Movie.objects.all()
    def list(self , request):
        movies = self.serializer_class(self.get_queryset() ,many=True)
        if request.query_params.get("limit") :
            limit = request.query_params.get("limit")[0]
            try :
                limit = int(limit)
            except ValueError:
                return Response({"error":"invalid limit"},status=status.HTTP_400_BAD_REQUEST)
            movies = self.serializer_class(self.get_queryset(limit=(limit)),many=True)
        return Response({"movies": movies.data},status=status.HTTP_200_OK)
    
class GenreListApiView(generics.ListAPIView):
    queryset = Genre.objects.all()
    serializer_class = GenresSerializer

class DirecotorListApiView(generics.ListAPIView):
    queryset = Directors.objects.all()
    serializer_class = DirectorsSerializer