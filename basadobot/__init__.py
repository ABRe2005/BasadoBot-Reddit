from basadobot.models import User, ParienteBasado, Pildora, OtherComment, session
from basadobot.security import security1, security2
from basadobot.data import reciber
import praw
from time import sleep

#Mensajes copiados de u/basedcount_bot momentaneamente.
messages = {
            1:"Casa de cartas",
            5:"Árbol joven",
            10:"Silla de oficina",
            20:"Canasta de baloncesto (llena de arena)",
            35:"Luchador de sumo",
            50:"Fundación de hormigón",
            75:"Sequoia gigante",
            100:"Empire State Building",
            200:"Gran pirámide de Giza",
            350:"Edificio de ensamblaje de vehículos de la ESA",
            500:"Fábrica de Boeing Everett",
            750:"Monte Fuji", 
            1000:"Denali",
            2000:"Annapurna"}

#Clase del bot, a partir de aqui se hace todo.
class bot:
    def __init__(self, **kwargs):
        #Instancia de reddit, desde ahí se leen los mensajes del subreddit.
        self.reddit = praw.Reddit(**kwargs)

    #Función para dar el basado (punto) y asignar por quien ha sido dado.
    def dar_basado(self, basado):

        #Un basadobot.models.ParienteBasado, None o False.
        pariente = security2(basado)

        #En caso de que pariente no exista, es decir que ese comentario no ha recibido un "basado" antes
        #se crea dicho pariente.
        if pariente == None:
            #El username del autor del comentario/post al cual ha sido comentado,
            #es decir, la persona que está basada.
            reci = basado.parent().author

            #Un basadobot.models.User o None.
            recibidor = session.query(User).filter(User.username == str(reci)).first()
            
            #Si existe (!None), se puede sumar 1, en caso contrario no se puede hacer.
            if recibidor:
                recibidor.basados += 1

            #Si no se puede hacer, crea un nuevo basadobot.models.User.
            else:
                recibidor = User(username=str(reci), basados=1)
            
            #Aqui crea el basadobot.models.ParienteBasado, ya que no estaba creado antes.
            pariente = ParienteBasado(parentId = basado.parent_id,
                        submissionId = basado.link_id,
                        isComment = basado.parent_id[1] == 1,
                        autor = recibidor
            )
        
        #En caso de que sea Falso significa que el basado no es valido por algun motivo.
        elif pariente == False:
            return

        #Finalmente, en caso de que exista el usuario, lo unico que hace es buscar 
        #la persona basada (basadobot.models.User), debido a que el pariente existia
        #tiene que existir el recibidor.
        else:
            recibidor = session.query(User).filter(User.id == pariente.autorId).first()
        
        #Un basadobot.models.User o None.
        commenter = session.query(User).filter(User.username == str(basado.author)).first()

        #En caso de que sea None, crea el que ha escrito "basado" (basadobot.models.User)
        if not commenter:
            commenter = User(username = str(basado.author))
        
        #Si la funcion de seguridad no da ningun error, procede a añadir los datos en la database
        if security1(commenter, pariente, recibidor):
            commenter.basadosHechos.append(pariente)
            session.add(commenter)
            session.add(pariente)
            session.add(recibidor)

            return recibidor

    #Self explainatory
    def commit_changes(self, changes=True):
        print("Commited changes!") if changes else print("Commited othercommands!")
        session.commit()

    #Funcion para dar las pildoras (en caso que tenga) cuando hay un basado
    def dar_pildoras(self, recibidor, basado, pillWord): 
        #Saca el nombre de la pill como tal
        nombrePill = basado.body.lower().split(pillWord)[0].split(" ")[-1]
        
        #Añade la pill a la db y se la da al que la recibe
        pill = Pildora(name=nombrePill, recibidor=recibidor)
        session.add(pill)
        return pill

    #Envia el mensaje anunciando el basado
    def mensaje_basado(self, recib):
        #Si tiene pildora y tiene subida de nivel asigna el mensaje a lo de abajo
        if recib.pill != None and recib.recibidor.basados in messages:
            message = "\n\n".join([
                f"¡El usuario u/{recib.recibidor.username} ha conseguido una pildora y ha subido de nivel a la vez!",
                f"La píldora es {recib.pill.name}.",
                f"Ahora es nivel {recib.recibidor.basados}:{messages.get(recib.recibidor.basados)}",
                f"Tiene las siguientes píldoras: {', '.join(list(map(lambda x: x.name, recib.recibidor.pildoras)))}"
            ])

        #Si tiene pildora y pero no subida asigna el mensaje a lo de abajo
        elif recib.pill != None:

            #Coge el numero de basados y consigue el nombre del ultimo rango conseguido
            num = recib.recibidor.basados
            nombre = messages.get(num)
            while not nombre:
                num -= 1
                nombre = messages.get(num)

            message = "\n\n".join([
                f"¡El usuario u/{recib.recibidor.username} ha conseguido una píldora!",
                f"La píldora es {recib.pill.name}.",
                f"Él es de nivel {recib.recibidor.basados}:{nombre}",
                f"Tiene las siguientes píldoras: {', '.join(list(map(lambda x: x.name, recib.recibidor.pildoras)))}"
            ])

        #Si tiene subida pero no tiene pildora asigna el mensaje a lo de abajo
        elif recib.recibidor.basados in messages:
            message = "\n\n".join([
                f"¡El usuario u/{recib.recibidor.username} ha subido de nivel!",
                f"Ahora es nivel {recib.recibidor.basados}:{messages.get(recib.recibidor.basados)}",
                f"Tiene las siguientes píldoras: {', '.join(list(map(lambda x: x.name, recib.recibidor.pildoras)))}"
            ])
        #Ultima parte del mensaje y lo envia al comentario
        message += "\n\n¿Alguna duda? ¡Haz /info o háblame por MD a mi o a mi creador!"
        recib.comment.reply(message)

    #Comprueba si cumple los requisitos para tener mensaje
    def comprobar_mensaje(self, receb) -> bool:
        return receb.pill != None or receb.recibidor.basados in messages

    #Mira los comentarios que contengan las palabras iniciales 
    def mirar_basados(self) -> list:
        nuevosBasados = []

        #Subreddit del donde buscara los mensajes
        subreddit_inspection = self.reddit.subreddit("BasadoBot")

        #Mira los ultimos 100 comentarios y en caso que inicie con la palabra deseada continua,
        #en caso contrario pasa de comentario, si encuentra la palabra tambien mira si tiene pildora
        for comment in subreddit_inspection.comments(limit=100):
            palabraEncontrada = ""
            for palabra in ["basado", "basada", "based"]:
                if palabra in comment.body.lower()[:len(palabra)]:
                    palabraEncontrada = palabra
                    break
            
            else:
                continue
            
            pildora = ""
            for palabra in ["pileado", "pilleado", "pildoreado", "pileada", "pilleada", "pildoreada", "pilled"]:
                if palabra in comment.body.lower()[len(palabraEncontrada):]:
                    pildora = palabra
                    break
            
            nuevosBasados.append([comment, pildora])

        return nuevosBasados

    #Funcion por hacer, mira otros comandos como info, usuariosmasbasados, cantidaddebasado, tirarpildora...
    def mirar_otros_comandos(self) -> list:
        comentarios = []

        #Subreddit del donde buscara los mensajes.
        subreddit_inspection = self.reddit.subreddit("BasadoBot")

        #Mira los ultimos 100 comentarios y en caso que inicie con "/" y no esté en la
        #database se añadirá a posibles respuestas.
        for comment in subreddit_inspection.comments(limit=100):
            if "/" == comment.body[0] and not session.query(OtherComment).filter(OtherComment.commentId == comment.id).first():
                session.add(OtherComment(commentId=comment.id))
                comentarios.append(comment)
        
        return comentarios

    #Funcion que responde a los comandos
    def responder_otros_comandos(self, comandos):
        for comando in comandos:
            if "info" == comando.body[1:5]:
                message = "\n\n".join([
                    "¡Hola! ¡Soy un bot llamado BasadoBot!",
                    "He sido creado por u/TheRepSter, por simple diversión.",
                    "Cuento \"basados\", es decir, cuando estás de acuerdo con una persona.",
                    "También llevo la cuenta de las pildoras que tiene cada usuario.",
                    "Los comandos son los siguientes:",
                    "- /info: muestra este mensaje.",
                    "- /usuariosmasbasados (o /usuariosmásbasados): muestra el top 10 de basados.",
                    "- /cantidaddebasado \{username\}: muestra los basados según el username",
                    "- /tirarpildora \{pildora\}: tira la pildora que mencione el usuario que pone el comando",
                    ""
                    "Soy de código abierto, es decir, ¡puedes ver mi código e incluso aportar!",
                    "[Haz click aqui para ver el código.](https://github.com/TheRepSter/BasadoBot)",
                    "¿Tienes alguna duda? ¡Háblame por MD a mi o a mi creador!"
                ])
            elif "usuariosmasbasados" == comando.body[1:19] or "usuariosmásbasados" == comando.body[1:19]:
                usuarios = session.query(User).order_by(User.basados.desc()).limit(10).all()
                message = "El Top 10 de los usuarios más basados es actualmente:\n\n"
                for numb, i in enumerate(usuarios):
                    message += f"{numb+1}. [{i.username}](https://reddit.com/user/{i.username}): {i.basados}\n\n"

            elif "cantidaddebasado" == comando.body[1:17]:
                toBuscar = comando.body.split(" ")[1]
                if "u/" in toBuscar:
                    toBuscar = toBuscar.split("/")[1]

                usuario = session.query(User).filter(User.username == toBuscar).first()
                if usuario:
                    message = f"El usuario {usuario.username} tiene {usuario.basados} basados."
                    message += f"\n\nTiene las siguientes píldoras: {', '.join(list(map(lambda x: x.name, usuario.pildoras)))}"

                else:
                    message = f"El usuario {toBuscar} no exise o no ha recibido ni hecho ningun basado."

            elif "tirarpildora" == comando.body[1:13]:
                autor = session.query(User).filter(User.username == str(comando.author)).first()
                toBuscar = comando.body.split(" ")[1]
                pills = session.query(Pildora).filter(Pildora.name == toBuscar).all()
                if pills:
                    for pill in pills:
                        if pill.recibidor.id == autor.id:
                            autor.pildoras.remove(pill)
                            session.add(autor)
                            message = f"La pildora {toBuscar} ha sido eliminada."
                            break
                    
                    else:
                        message = f"¡No tienes la pildora {toBuscar}!"
                else:
                    message = f"¡No tienes la pildora {toBuscar}!"
                
            else:
                continue

            comando.reply(message)

    #Funcion principal del bot
    def run(self):
        while True:
            recibidores = []

            basadosActuales = self.mirar_basados()
            for basado in basadosActuales:
                recibe = self.dar_basado(basado[0])
                if not recibe:
                    continue

                pill = None
                if basado[1]:
                    pill = self.dar_pildoras(recibe, basado[0], basado[1])

                recibidores.append(reciber(recibe, basado[0], pill))

            if len(recibidores):
                self.commit_changes()

            for receb in recibidores:
                if self.comprobar_mensaje(receb):
                    sleep(1)
                    self.mensaje_basado(receb)

            otros_comandos = self.mirar_otros_comandos()
            self.responder_otros_comandos(otros_comandos)
            if len(otros_comandos):
                self.commit_changes(False)
            sleep(10)